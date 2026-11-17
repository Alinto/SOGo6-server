from __future__ import annotations
from typing import TYPE_CHECKING

from hashlib import sha256
import hmac
from unicodedata import combining, normalize

from app.dav.DavConst import DAV_LOGIN_BLOCKED_PREFIX, DAV_LOGIN_FAILURE_PREFIX
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_dav
from app.utils.maths.crypto_utils import get_encryption_key

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import AuthSettingsObj
    from app.manager.cache.ClientRedis import ClientRedis


class DavLoginLimiter:
    """Block the DAV logins of an account after too many wrong passwords.

    Only distinct wrong passwords count: a device still sending an old password counts once. A correct
    password does not reset the count, a client syncing every few minutes would otherwise clear it before
    an attacker reaches the limit.
    """

    def __init__(self, cache: ClientRedis) -> None:
        self._cache: ClientRedis = cache

    def check_not_blocked(self, login: str, auth_settings: AuthSettingsObj) -> None:
        """Refuse a blocked login, before its password is tried.

        :param login: The login of the request
        :type login: str
        :param auth_settings: Authentication settings of the login domain, SOGO_D_LOGIN_CHECK_MAX_ATTEMPT at 0
            turns the blocking off
        :type auth_settings: AuthSettingsObj
        :raises RequestException: ERROR_DAV_LOGIN_BLOCKED while the login is blocked
        """
        if auth_settings.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT == 0:
            return
        blocked_key: str = DAV_LOGIN_BLOCKED_PREFIX + DavLoginLimiter._login_key(login)
        if self._cache.get(blocked_key, expected_type=str) is not None:
            raise RequestException(error=err.ERROR_DAV_LOGIN_BLOCKED)

    def record_failure(self, login: str, password: str, auth_settings: AuthSettingsObj) -> None:
        """Count a wrong password of the login, and block the login once the limit is reached.

        The fingerprints of the wrong passwords are the fields of a hash: requests sent in parallel add
        theirs without overwriting the others, and a password already sent is counted once. Each wrong
        password restarts the time to live of the hash.

        :param login: The login of the request
        :type login: str
        :param password: The wrong password, only its fingerprint is kept
        :type password: str
        :param auth_settings: Authentication settings of the login domain, with the number of wrong passwords
            (SOGO_D_LOGIN_CHECK_MAX_ATTEMPT), the time to live of the count (SOGO_D_LOGIN_CHECK_TIME_SPAN) and
            the length of the block (SOGO_D_LOGIN_CHECK_BLOCK_TIME), in seconds
        :type auth_settings: AuthSettingsObj
        """
        if auth_settings.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT == 0:
            return
        login_key: str = DavLoginLimiter._login_key(login)
        failure_key: str = DAV_LOGIN_FAILURE_PREFIX + login_key
        self._cache.hashset(
            key=failure_key,
            data={DavLoginLimiter._fingerprint(password): "1"},
            ttl=auth_settings.SOGO_D_LOGIN_CHECK_TIME_SPAN,
        )
        failures: int = len(self._cache.hashget(failure_key) or {})
        if failures < auth_settings.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT:
            return
        self._cache.set(
            key=DAV_LOGIN_BLOCKED_PREFIX + login_key, value="1", ttl=auth_settings.SOGO_D_LOGIN_CHECK_BLOCK_TIME
        )
        self._cache.delete(failure_key)
        logger_dav.warning(
            "Login %s blocked for %d s after %d wrong passwords",
            login,
            auth_settings.SOGO_D_LOGIN_CHECK_BLOCK_TIME,
            failures,
        )

    @staticmethod
    def _login_key(login: str) -> str:
        """Key of the counters of a login.

        User sources match logins ignoring case (LDAP caseIgnoreMatch with the string preparation of RFC 4518,
        default MariaDB collations), and the default MariaDB collations ignore accents as well: the variants
        of a login share its counters.
        """
        folded: str = normalize("NFKD", normalize("NFKD", login).casefold())
        return "".join(char for char in folded if not combining(char))

    @staticmethod
    def _fingerprint(password: str) -> str:
        """Keyed fingerprint of a wrong password: without the key, a dump of the cache cannot be brute-forced
        to find the passwords, often typos of the right one. The key is derived from the encryption key, so
        that this one does not serve as is for a second purpose."""
        key: bytes = hmac.new(get_encryption_key(), b"dav login failure", sha256).digest()
        return hmac.new(key, password.encode("utf-8"), sha256).hexdigest()
