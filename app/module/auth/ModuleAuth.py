from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Type
from urllib.parse import urlencode, urlsplit, urlunsplit


from app.auth.User import User
from app.auth.service.VoucherUserService import VoucherUserService
from app.config.db import tables as tbl
from app.config.settings.DomainSettings import AuthSettings, AuthSettingsObj, UserSourceSettings, UserSourceSettingsObj
from app.module.auth.identity_provider import IdentityProvider
from app.module.auth.ModuleUserSource import ModuleUserSource
from app.module.auth.openid_provider import OpenIDProvider
from app.service import sogo_cache
from app.utils.db.Condition import EqualCondition
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_auth
from app.utils.strings import get_domain_from_mail
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import AuthSettingsObj, UserSourceSettingsObj
    from app.config.settings.SystemSettings import SystemSettingsObj
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL

#Identity providers for SSO, by SOGO_D_AUTH_TYPE
IDENTITY_PROVIDERS: dict[str, Type[IdentityProvider]] = {
    OpenIDProvider.kind: OpenIDProvider,
}
#Domain used in the SSO callback url when there is no domain (SOGO_S_DOMAINLESS_LOGIN)
SSO_NO_DOMAIN = "none"


def _get_origin(url:str) -> str:
    """
    Return the origin (scheme://host[:port]) of an url, lower case, empty if the url is not http(s)

    :param url: The url
    :type url: str
    :return: The origin or empty string
    :rtype: str
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}".lower()


def build_ui_redirect_url(ui_redirect:str, params:dict) -> str:
    """
    Put the parameters in the fragment of the UI url (its own fragment is replaced, its query is kept).
    The fragment is never sent to a server nor in the Referer header, so the jwt token does not end in access logs.

    :param ui_redirect: UI url
    :type ui_redirect: str
    :param params: Parameters to put in the fragment
    :type params: dict
    :return: The full url
    :rtype: str
    """
    parts = urlsplit(ui_redirect)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, urlencode(params)))


class ModuleAuth:  # pylint: disable=too-many-instance-attributes
    """
    Module to handle authentication. Thos module only take one user source.
    """
    def __init__(self, process: ProcessSetting,
                 system: SystemSettingsObj,
                 default_auth_settings: AuthSettingsObj,
                 default_us_source: dict[str, UserSourceSettingsObj]):
        """
        Initialize the authentication module

        :param process: Process settings
        :type process: ProcessSetting
        :param system: System settings object
        :type system: SystemSettingsObj
        :param default_auth_settings: Default authentication settings
        :type default_auth_settings: AuthSettingsObj
        :param default_us_source: Default user source settings mapped by source UID
        :type default_us_source: dict[str, UserSourceSettingsObj]
        """
        self.process_settings = process

        self.do_domains     = system.SOGO_S_DO_DOMAIN
        self.domainless     = system.SOGO_S_DOMAINLESS_LOGIN
        self.known_domains  = system.SOGO_S_KNOWN_DOMAIN
        self.reject_unknown = system.SOGO_S_REJECT_UNKNOWN_DOMAIN
        self.allowed_redirect_origins = {_get_origin(url) for url in system.SOGO_S_OPENID_ALLOW_REDIRECT} - {""}

        #UI url of the last SSO callback, known once the identity provider has read its state, even if the login failed
        self.sso_ui_redirect = ""

        self.default_auth = default_auth_settings
        self.default_us = default_us_source

    def _check_domain(self, uid:str) -> str:
        """
        Check if a domain is found and if it matches system settings rules

        :param uid: The user unique ID
        :type uid: str
        :raises RequestException: When no domain is given but domainless login is disabled
        :raises RequestException: When domain is not in known domains and unknown domains are rejected
        :return: empty string or the domain
        :rtype: str
        """
        domain = ""
        if not self.domainless:
            tmp_domain = get_domain_from_mail(uid)
            if not tmp_domain:
                raise RequestException("No domain given for auth when this is required")
            if self.reject_unknown and tmp_domain not in self.known_domains:
                raise RequestException("Domain given for auth is not registered in SOGO_S_REJECT_UNKNOWN_DOMAIN")
            domain = tmp_domain
        return domain

    def _get_domain_auth_and_user_source_settings(self, domain:str) -> tuple[AuthSettingsObj, dict[str, UserSourceSettingsObj]]:
        """
        Return the authentication and user source settings for this domain, or the default ones

        :param domain: The domain name
        :type domain: str
        :return: Tuple containing auth settings and user source settings mapped by source UID
        :rtype: tuple[AuthSettingsObj, dict[str, UserSourceSettingsObj]]
        """
        domain_auth_settings = self.default_auth
        domain_user_source = self.default_us
        if domain and self.do_domains:
            fake_process_settings_db = self.process_settings.SOGO_P_DB_TYPE
            sogo_db_type = f"Client{fake_process_settings_db}"

            sogo_db_manager: ClientSQL = import_and_instantiate_manager(module_path="app.manager.db",
                                                            module_and_class_name=sogo_db_type,
                                                            module_args=self.process_settings.get_db_settings())
            condition = EqualCondition(tbl.COL_DOMAIN_NAME.name, domain)
            sogo_db_manager.connect()
            result = list(sogo_db_manager.select_from_table(tbl.TABLE_DOMAIN,
                                                [tbl.COL_DOMAIN_SETTINGS],
                                                condition=condition))
            if len(result) == 1:
                domain_auth_settings = AuthSettingsObj(result[0][0][AuthSettings.subparent]) #result[0][0]: first column of the first row of the result
                domain_user_source_raw = result[0][0][UserSourceSettings.subparent]
                domain_user_source = {}
                for source_uid, source_settings in domain_user_source_raw.items():
                    domain_user_source[source_uid] = UserSourceSettingsObj(source_settings)

        return domain_auth_settings, domain_user_source

    def _check_callback_domain(self, domain:str) -> str:
        """
        Check the domain given in a SSO callback url, the same way _check_domain does for a uid

        :param domain: The domain from the callback url
        :type domain: str
        :raises RequestException: When domain is not in known domains and unknown domains are rejected
        :return: empty string or the domain
        :rtype: str
        """
        if self.domainless:
            return ""
        if self.reject_unknown and domain not in self.known_domains:
            raise RequestException("Domain given for auth is not registered in SOGO_S_REJECT_UNKNOWN_DOMAIN")
        return domain

    def is_ui_redirect_allowed(self, ui_redirect:str) -> bool:
        """
        Check that the origin of the UI url is exactly one of SOGO_S_OPENID_ALLOW_REDIRECT

        :param ui_redirect: UI url given by the UI
        :type ui_redirect: str
        :return: True if the UI url can be used as redirection
        :rtype: bool
        """
        origin = _get_origin(ui_redirect)
        print("Origin of UI redirect:", origin)
        print("Allowed redirect origins:", self.allowed_redirect_origins)
        return bool(origin) and origin in self.allowed_redirect_origins

    @staticmethod
    def _get_identity_provider(auth_settings:AuthSettingsObj, callback_url:str) -> IdentityProvider|None:
        """
        Return the identity provider for this domain, None if the authentication is not a SSO (plain)

        :param auth_settings: Authentication settings of the domain
        :type auth_settings: AuthSettingsObj
        :param callback_url: API url called by the identity provider after the user logged in
        :type callback_url: str
        :return: The identity provider or None
        :rtype: IdentityProvider|None
        """
        provider_class = IDENTITY_PROVIDERS.get(auth_settings.SOGO_D_AUTH_TYPE)
        if provider_class is None:
            return None
        return provider_class(auth_settings, callback_url)

    def get_login_mech(self, uid:str, ui_redirect:str, callback_url_builder:Callable[[str, str], str]) -> dict:
        """
        Get the login mechanism for this uid

        :param uid: username/mail/uid of the user
        :type uid: str
        :param ui_redirect: UI url where the user is sent back after a SSO login, ignored for plain
        :type ui_redirect: str
        :param callback_url_builder: Function (kind, domain) -> url of the API callback for SSO
        :type callback_url_builder: Callable[[str, str], str]
        :raises RequestException: If the domain is invalid or ui_redirect is not allowed for a SSO
        :return: Dictionary containing the authentication kind and location
        :rtype: dict
        """
        print("######## Getting login mechanism ########")
        domain = self._check_domain(uid)
        domain_auth_settings, _ = self._get_domain_auth_and_user_source_settings(domain)
        kind = domain_auth_settings.SOGO_D_AUTH_TYPE

        location = ""
        callback_url = callback_url_builder(kind, domain) # or SSO_NO_DOMAIN)
        provider = self._get_identity_provider(domain_auth_settings, callback_url)
        if provider:
            if not self.is_ui_redirect_allowed(ui_redirect):
                logger_auth.warning("SSO login asked with a redirect not in SOGO_S_OPENID_ALLOW_REDIRECT: %s", ui_redirect)
                raise RequestException(error=err.ERROR_SSO_REDIRECT_NOT_ALLOWED)
            location = provider.get_login_location(ui_redirect)

        #TODO cas
        ret = {
            "kind": kind,
            "SOGO_D_PWD_RECOVERY": domain_auth_settings.SOGO_D_PWD_RECOVERY,
            "location": location
        }
        return ret

    def get_user_from_sso_callback(self, kind:str, domain:str, callback_data:dict,
                                   callback_url_builder:Callable[[str, str], str]) -> tuple[User, dict[str, UserSourceSettingsObj]]:
        """
        Authenticate a user with the data sent by the identity provider on the SSO callback

        :param kind: Kind of SSO of the callback (openid, saml2...)
        :type kind: str
        :param domain: Domain given in the callback url
        :type domain: str
        :param callback_data: Data received on the callback (query parameters for openid)
        :type callback_data: dict
        :param callback_url_builder: Function (kind, domain) -> url of the API callback for SSO
        :type callback_url_builder: Callable[[str, str], str]
        :raises RequestException: If the state is invalid, the domain is not configured for this SSO or the authentication failed
        After the call, sso_ui_redirect is the UI url kept with the state if it could be read (and is still allowed).
        :return: Tuple of (authenticated User, domain user sources settings)
        :rtype: tuple[User, dict[str, UserSourceSettingsObj]]
        """
        callback_domain = domain
        domain = self._check_callback_domain(domain)
        domain_auth_settings, domain_user_sources = self._get_domain_auth_and_user_source_settings(domain)
        if domain_auth_settings.SOGO_D_AUTH_TYPE != kind:
            raise RequestException(error=err.ERROR_SSO_WRONG_AUTH_TYPE)

        #redirect_uri must be exactly the same as the one given in get_login_mech, the state is bound to it
        provider = self._get_identity_provider(domain_auth_settings, callback_url_builder(kind, callback_domain))
        if provider is None:
            raise RequestException(error=err.ERROR_SSO_WRONG_AUTH_TYPE)
        try:
            identity = provider.authenticate_from_callback(callback_data)
        finally:
            #Checked again: SOGO_S_OPENID_ALLOW_REDIRECT may have changed since get_login_mech
            if self.is_ui_redirect_allowed(provider.ui_redirect):
                self.sso_ui_redirect = provider.ui_redirect
            elif provider.ui_redirect:
                logger_auth.warning("SSO state with a redirect not in SOGO_S_OPENID_ALLOW_REDIRECT anymore: %s", provider.ui_redirect)

        #The access token is kept as password to authenticate on the mail servers (xoauth2)
        if self.domainless:
            user = User(identity.mail, identity.access_token, is_domainless=True)
        else:
            user = User(identity.mail, identity.access_token, domain=domain)
        user.mail = identity.mail
        user.auth_kind = kind

        #The identity provider authenticated the user, the user sources give its uid, cn, source_id...
        module_us = ModuleUserSource(domain_user_sources)
        if not module_us.check_user_without_password(user):
            logger_auth.info("SSO user %s not found in the user sources", identity.mail)
            raise RequestException(error=err.ERROR_SSO_USER_NOT_FOUND)
        if domain and user.domain != domain:
            logger_auth.warning("SSO user %s found with domain %s but the callback is for domain %s", identity.mail, user.domain, domain)
            raise RequestException(error=err.ERROR_SSO_LOGIN_FAILED)

        return user, domain_user_sources

    def get_user_and_domain_user_sources(self, username:str, password:str) -> tuple[User, dict[str, UserSourceSettingsObj]]:
        """
        Prepare a User object for plain login authentication and get the domain user sources

        :param username: username/mail/uid of the user
        :type username: str
        :param password: password
        :type password: str
        :return: Tuple of (User object ready for authentication, domain user sources settings)
        :rtype: tuple[User, dict[str, UserSourceSettingsObj]]
        """

        domain = self._check_domain(username)
        _, domain_user_sources = self._get_domain_auth_and_user_source_settings(domain)

        if self.domainless:
            user = User(username, password, is_domainless=True)
        else:
            user = User(username, password, domain=domain)

        return user, domain_user_sources

    def generate_voucher_from_user(self, user: User) -> dict:
        """
        Generate a voucher from an authenticated user

        :param user: Authenticated user object
        :type user: User
        :return: Dictionary containing the jwt_token
        :rtype: dict
        """
        voucher_user_service = VoucherUserService(self.process_settings)
        voucher_data = voucher_user_service.generate_voucher_from_user(user)
        return {"jwt_token": voucher_data}

    def logout_user(self, voucher_data: str) -> None:
        """
        Revoke the session associated with the given voucher.

        :param voucher_data: The raw voucher (JWT token) from the Authorization header
        :type voucher_data: str
        :raises RequestException: If the voucher is invalid or the session cannot be revoked
        """
        voucher_user_service = VoucherUserService(self.process_settings)
        redis_key = voucher_user_service.get_redis_session_key_from_voucher(voucher_data)

        cache = sogo_cache()
        cache.revoke_user_sessions_by_key([redis_key])
        cache.close()
