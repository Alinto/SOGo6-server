from __future__ import annotations
from typing import TYPE_CHECKING
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from json import dumps as js_dumps, loads as js_loads, JSONDecodeError
from uuid import uuid4

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.auth.User import User
from app.auth.voucher.JWTVoucher import JWTVoucher
from app.service import sogo_cache
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import AggravatedException, BugException, RequestException
from app.utils.logger.logger import logger_auth
from app.utils.maths.sogo_hash import get_unique_token

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


_STAGE_TTL = {
    cs.MFA_STAGE_VERIFY: cs.TTL_MFA_SESSION_VERIFY,
    cs.MFA_STAGE_ENROLL: cs.TTL_MFA_SESSION_ENROLL,
}


@dataclass
class MfaSession:  # pylint: disable=too-many-instance-attributes
    """
    MFA session: exists between a valid password and a valid second factor.
    It is never accepted as a user session.

    session_key decrypts the user session data (password included) kept in the cache.
    It only travels inside the voucher, never stored in the cache.
    """
    session_id: str
    session_key: str
    uid: str
    mail: str
    domain: str
    stage: str
    provider: str = ""
    challenge: dict = field(default_factory=dict)
    allowed_methods: list[str] = field(default_factory=list)

    @property
    def redis_key(self) -> str:
        """
        Key of this MFA session in the cache
        """
        return f"{cs.MFA_SESSION_PREFIX}{self.session_id}"


class VoucherMfaService:
    """
    Create, read and consume MFA sessions and their voucher.

    Same design as VoucherUserService: the cache keeps the user session data encrypted with a
    per-session key, and the voucher (JWT) holds this key encrypted with SOGO_P_VOUCHER_SECRET.
    The voucher has the claim kind=mfa so it can never be confused with a user voucher.
    """

    def __init__(self, process_settings: ProcessSetting):
        secret: str = process_settings.SOGO_P_VOUCHER_SECRET
        if len(secret) != 32:
            raise AggravatedException("SOGO_P_VOUCHER_SECRET is not 32 char long")
        self.fernet_session = Fernet(urlsafe_b64encode(secret.encode("utf-8")))
        self.voucher = JWTVoucher(secret)

    @staticmethod
    def is_mfa_voucher(voucher_data: str | None) -> bool:
        """
        Tell if a voucher is an MFA one, WITHOUT checking it. Only used to route the voucher
        to the right service, which then checks it.

        :param voucher_data: raw voucher from the Authorization header
        :type voucher_data: str | None
        :return: True if the voucher claims to be an MFA voucher
        :rtype: bool
        """
        if not isinstance(voucher_data, str):
            return False
        try:
            claims = jwt.decode(voucher_data, options={"verify_signature": False})
        except jwt.PyJWTError:
            return False
        return claims.get(cs.MFA_KIND_CLAIM) == cs.MFA_KIND

    def create(self, user: User, stage: str, provider: str = "",  # pylint: disable=too-many-locals
               challenge: dict | None = None, allowed_methods: list[str] | None = None) -> str:
        """
        Create the MFA session for a user whose password has been checked, and return its voucher

        :param user: user authenticated by password
        :type user: User
        :param stage: cs.MFA_STAGE_VERIFY or cs.MFA_STAGE_ENROLL
        :type stage: str
        :param provider: id of the provider to verify (stage verify)
        :type provider: str
        :param challenge: challenge state returned by the provider (stage verify)
        :type challenge: dict | None
        :param allowed_methods: methods the user can choose from (stage enroll)
        :type allowed_methods: list[str] | None
        :raises BugException: unknown stage or encryption failure
        :return: the voucher to send to the client
        :rtype: str
        """
        if stage not in _STAGE_TTL:
            raise BugException(f"Unknown MFA stage {stage}")
        ttl = _STAGE_TTL[stage]

        session_id = str(uuid4())
        session_key = get_unique_token(32)
        try:
            session_fernet = Fernet(urlsafe_b64encode(session_key.encode("utf-8")))
            sensitive_data = session_fernet.encrypt(js_dumps(user.get_user_session()).encode("utf-8"))
            voucher_session_token = self.fernet_session.encrypt(f"{session_id}:{session_key}".encode("utf-8"))
        except (ValueError, InvalidToken) as e:
            raise BugException("Cannot encrypt MFA session") from e

        mfa_session = {
            cs.USER_UID: user.uid,
            cs.USER_DOMAIN: user.domain,
            cs.USER_EMAIL: user.mail,
            "stage": stage,
            "provider": provider,
            "challenge": js_dumps(challenge or {}),
            "allowed_methods": js_dumps(allowed_methods or []),
            "attempts": 0,
            cs.SESSION_SENSITIVE: sensitive_data.decode("utf-8"),
        }
        cache = sogo_cache()
        try:
            cache.hashset(f"{cs.MFA_SESSION_PREFIX}{session_id}", mfa_session, ttl)
        finally:
            cache.close()

        payload = {
            cs.USER_UID: user.uid,
            cs.MFA_KIND_CLAIM: cs.MFA_KIND,
            cs.MFA_STAGE_CLAIM: stage,
            cs.SESSION_KEY: voucher_session_token.decode("utf-8"),
        }
        return self.voucher.create_voucher(payload, ttl)

    def read_session(self, voucher_data: str | None) -> MfaSession | None:
        """
        Check an MFA voucher and return its MFA session

        :param voucher_data: raw voucher from the Authorization header
        :type voucher_data: str | None
        :return: the MFA session, None if the voucher is invalid/expired or the session is gone
        :rtype: MfaSession | None
        """
        if not isinstance(voucher_data, str) or not self.voucher.check_voucher_data_type(voucher_data):
            return None
        payload = self.voucher.read_voucher(voucher_data)
        if not payload or payload.get(cs.MFA_KIND_CLAIM) != cs.MFA_KIND:
            return None

        try:
            session_key_raw = self.fernet_session.decrypt(payload[cs.SESSION_KEY].encode("utf-8")).decode("utf-8")
            session_id, session_key = session_key_raw.split(":")
        except (KeyError, ValueError, InvalidToken, AttributeError):
            logger_auth.warning("MFA voucher with an invalid session key")
            return None

        cache = sogo_cache()
        try:
            data = cache.hashget(f"{cs.MFA_SESSION_PREFIX}{session_id}")
        finally:
            cache.close()
        if not data:
            logger_auth.info("MFA session for %s is expired or does not exist", payload.get(cs.USER_UID))
            return None

        if data.get(cs.USER_UID) != payload.get(cs.USER_UID) or data.get("stage") != payload.get(cs.MFA_STAGE_CLAIM):
            logger_auth.warning("MFA voucher does not match its MFA session")
            return None

        try:
            challenge = js_loads(data.get("challenge") or "{}")
            allowed_methods = js_loads(data.get("allowed_methods") or "[]")
        except JSONDecodeError as e:
            raise BugException("MFA session data is not a json") from e

        return MfaSession(session_id=session_id,
                          session_key=session_key,
                          uid=data[cs.USER_UID],
                          mail=data.get(cs.USER_EMAIL, ""),
                          domain=data.get(cs.USER_DOMAIN, ""),
                          stage=data["stage"],
                          provider=data.get("provider", ""),
                          challenge=challenge,
                          allowed_methods=allowed_methods)

    def register_failure(self, mfa_session: MfaSession) -> int:
        """
        Count one more failed code on this MFA session

        :return: the number of failed attempts
        :rtype: int
        """
        cache = sogo_cache()
        try:
            return cache.hash_incr(mfa_session.redis_key, "attempts")
        finally:
            cache.close()

    def delete(self, mfa_session: MfaSession) -> None:
        """
        Delete the MFA session (the user must log in again)
        """
        cache = sogo_cache()
        try:
            cache.delete(mfa_session.redis_key)
        finally:
            cache.close()

    def consume(self, mfa_session: MfaSession) -> User:
        """
        Delete the MFA session and return the user it was created for,
        so the user session can be issued. Only one concurrent call can succeed.

        :raises RequestException: the MFA session is gone (expired or already consumed)
        :return: the user, with the data needed to create the user session
        :rtype: User
        """
        cache = sogo_cache()
        try:
            data = cache.hashget(mfa_session.redis_key)
            deleted = cache.delete(mfa_session.redis_key) if data else 0
        finally:
            cache.close()
        if not data or deleted != 1:
            raise RequestException(err.ERROR_MFA_SESSION_INVALID.m, err.ERROR_MFA_SESSION_INVALID)

        try:
            session_fernet = Fernet(urlsafe_b64encode(mfa_session.session_key.encode("utf-8")))
            user_data = js_loads(session_fernet.decrypt(data[cs.SESSION_SENSITIVE]))
        except (ValueError, InvalidToken, KeyError) as e:
            raise RequestException(err.ERROR_MFA_SESSION_INVALID.m, err.ERROR_MFA_SESSION_INVALID) from e

        return User.init_from_user_session(user_data)
