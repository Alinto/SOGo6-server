from __future__ import annotations
from typing import TYPE_CHECKING

from base64 import b64decode

from app.auth.User import User
from app.config.init_config import init_get_system_and_default_domain_settings, init_get_user_domain_settings
from app.config.settings.DomainSettings import AuthSettings, AuthSettingsObj
from app.config.settings.SystemSettings import SystemSettings, SystemSettingsObj
from app.dav.DavConst import DAV_LOGIN_FORBIDDEN_CHARS
from app.dav.DavLoginLimiter import DavLoginLimiter
from app.dav.model.DavContext import DavContext
from app.interface.auth.InterfaceAuthUser import InterfaceAuthUser
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_dav
from app.utils.strings import get_domain_from_mail

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.dav.model.DavRequest import DavRequest
    from app.manager.cache.ClientRedis import ClientRedis


class DavAuthenticator:
    """Authenticate DAV requests with HTTP Basic and build their context.

    Clients send their credentials with every request, there is no session: like the REST API does with
    the user of a voucher, the credentials are checked against the user source on every request.
    """

    def __init__(self, process_settings: ProcessSetting, require_secure: bool = True) -> None:
        self._process_settings: ProcessSetting = process_settings
        self._require_secure: bool = require_secure

    def authenticate(self, request: DavRequest, cache: ClientRedis) -> DavContext:
        """
        Check the Basic credentials of the request and build its context.

        Basic credentials travel in clear and are refused without TLS (RFC 4918 section 20.1, RFC 4791
        section 11). That refusal is a 403: a 401 would carry the Basic challenge, forbidden as well.

        :param request: The DAV request
        :type request: DavRequest
        :param cache: The cache client of the request, keeping the wrong passwords and the blocked logins
        :type cache: ClientRedis
        :raises RequestException: 403 without TLS or when the domain of the login refuses passwords, 401
            when the credentials are missing, malformed or refused, or when the domain of the account refuses
            passwords, 429 while the login is blocked
        :return: The context of the request, with the authenticated user
        :rtype: DavContext
        """
        if self._require_secure and not request.secure:
            raise RequestException(error=err.ERROR_DAV_INSECURE_CONNECTION)
        login, password = DavAuthenticator._parse_basic(request.headers.get("authorization", ""))
        login = DavAuthenticator._normalize_login(login)
        if not password:
            # An empty password asks LDAP for an unauthenticated bind (RFC 4513 section 5.1.2), that some
            # directories grant without checking anything
            raise RequestException(error=err.ERROR_LOGIN_FAILED)

        system_settings, default_domain_settings = init_get_system_and_default_domain_settings()
        DavAuthenticator._check_login_domain(login, SystemSettingsObj(system_settings[SystemSettings.subparent]))
        user: User = User(login, password)
        user_domain_settings: dict = init_get_user_domain_settings(user, default_domain_settings)
        auth_settings: AuthSettingsObj = AuthSettingsObj(user_domain_settings[AuthSettings.subparent])
        if not DavAuthenticator._password_login_allowed(auth_settings):
            # The password would bypass the identity provider and its second factor, it is never tried
            raise RequestException(error=err.ERROR_DAV_PASSWORD_LOGIN_DISABLED)
        limiter: DavLoginLimiter = DavLoginLimiter(cache)
        limiter.check_not_blocked(login=login, auth_settings=auth_settings)

        interface: InterfaceAuthUser = InterfaceAuthUser(
            process=self._process_settings, system=system_settings, default_domain=user_domain_settings, user=user
        )
        # TODO cache the user source check, shared with the REST API
        creds_ok, user_found = interface.check_user_and_fill_info(user)
        if not creds_ok:
            limiter.record_failure(login=login, password=password, auth_settings=auth_settings)
            raise RequestException(error=err.ERROR_LOGIN_FAILED)
        user_found.domain = user_found.domain.lower()
        if user_found.domain != user.domain:
            # The login only chose the user source: the account may belong to another domain, whose rules apply.
            # The password has been checked: a refusal other than the one of a wrong password would confirm it.
            user_domain_settings = init_get_user_domain_settings(user_found, default_domain_settings)
            account_auth_settings: AuthSettingsObj = AuthSettingsObj(user_domain_settings[AuthSettings.subparent])
            if not DavAuthenticator._password_login_allowed(account_auth_settings):
                logger_dav.info(
                    "Login %s refused, the domain %s of the account refuses passwords", login, user_found.domain
                )
                limiter.record_failure(login=login, password=password, auth_settings=auth_settings)
                raise RequestException(error=err.ERROR_LOGIN_FAILED)
        return DavContext(
            process_settings=self._process_settings,
            system_settings=system_settings,
            user_domain_settings=user_domain_settings,
            user=user_found,
            cache=cache,
        )

    @staticmethod
    def _parse_basic(header: str) -> tuple[str, str]:
        """Extract login and password from an Authorization header (RFC 7617 section 2).

        A login cannot contain a colon, a password can: the credentials are split on the first one.
        """
        if not header:
            raise RequestException(error=err.ERROR_AUTHENTICATED_ROUTE)
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "basic":
            raise RequestException(error=err.ERROR_WRONG_AUTHORIZATION_TYPE)
        try:
            credentials: str = b64decode(token.strip(), validate=True).decode("utf-8")
        except ValueError as ex:
            raise RequestException(error=err.ERROR_WRONG_AUTHORIZATION_TYPE) from ex
        login, separator, password = credentials.partition(":")
        if not separator or not login:
            raise RequestException(error=err.ERROR_WRONG_AUTHORIZATION_TYPE)
        return login, password

    @staticmethod
    def _normalize_login(login: str) -> str:
        """Refuse the logins that would alter the queries of the user source, and lower the case of the
        domain (RFC 4343): the domain settings are looked up with the exact domain name.

        Logins with a space, a non-printable character (control, invisible), more than one "@", a leading
        "#" or a character of ``DAV_LOGIN_FORBIDDEN_CHARS`` are refused like a wrong password. A space would
        change the domain looked up in the settings, while LDAP ignores it. The local part is kept as is.
        """
        if (
            not login.isprintable()
            or login.count("@") > 1
            or login.startswith("#")
            or any(char.isspace() or char in DAV_LOGIN_FORBIDDEN_CHARS for char in login)
        ):
            raise RequestException(error=err.ERROR_LOGIN_FAILED)
        local_part, separator, domain = login.partition("@")
        return local_part + separator + domain.lower()

    @staticmethod
    def _check_login_domain(login: str, system_settings: SystemSettingsObj) -> None:
        """Refuse like a wrong password the logins that the domain rules of the user sources refuse: no domain
        while domainless logins are off, unknown domain while unknown domains are rejected. The user sources
        raise these refusals without error code, a 500 that clients do not take for a wrong login."""
        if system_settings.SOGO_S_DOMAINLESS_LOGIN:
            return
        domain: str | None = get_domain_from_mail(login)
        if not domain or (
            system_settings.SOGO_S_REJECT_UNKNOWN_DOMAIN and domain not in system_settings.SOGO_S_KNOWN_DOMAIN
        ):
            raise RequestException(error=err.ERROR_LOGIN_FAILED)

    @staticmethod
    def _password_login_allowed(auth_settings: AuthSettingsObj) -> bool:
        """Whether the domain checks passwords against its user sources (not an identity provider)."""
        return auth_settings.SOGO_D_AUTH_TYPE == cs.AUTH_TYPE_PLAIN
