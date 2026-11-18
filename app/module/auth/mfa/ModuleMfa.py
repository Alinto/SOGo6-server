from __future__ import annotations
from typing import TYPE_CHECKING, Any, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from json import loads as js_loads, JSONDecodeError

from app.auth.service.VoucherMfaService import VoucherMfaService
from app.auth.service.VoucherUserService import VoucherUserService
from app.config.db import tables as tbl
from app.module.auth.mfa.MfaCrypto import MfaCrypto
from app.module.auth.mfa.MfaProvider import MfaContext, MfaProvider
from app.module.auth.mfa.registry import get_provider_class
from app.module.common_module import get_sogo6_database
from app.service import sogo_cache
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import AggravatedException, BugException, RequestException
from app.utils.logger.logger import logger_mfa

if TYPE_CHECKING:
    from app.auth.User import User
    from app.auth.service.VoucherMfaService import MfaSession
    from app.config.settings.DomainSettings import AuthSettingsObj
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis
    from app.manager.db.ClientSQL import ClientSQL


MFA_ACTION_NONE = "none"      #No second factor: issue the user session
MFA_ACTION_VERIFY = "verify"  #The user has an active method: ask its code
MFA_ACTION_ENROLL = "enroll"  #MFA enforced and no active method: the user must set one up


@dataclass
class MfaDecision:
    """
    What the login must do after a valid password
    """
    action: str
    provider: str = ""
    method: dict = field(default_factory=dict)
    allowed_methods: list[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ModuleMfa:
    """
    Orchestrate the MFA: settings, user's method (column mfa_method), enrollment, login challenge,
    rate limiting and audit log. The providers only implement the method itself.

    No endpoint takes the method at login: it is worked out from the domain settings
    and the user's active method.
    """

    def __init__(self, process_settings: ProcessSetting, auth_settings: AuthSettingsObj | None = None):
        """
        :param process_settings: process settings
        :type process_settings: ProcessSetting
        :param auth_settings: effective auth settings of the user's domain. Can be None for
                              operations that don't depend on them (admin reset)
        :type auth_settings: AuthSettingsObj | None
        """
        self.process_settings = process_settings
        self.auth_settings = auth_settings
        self.sogo_db_manager: ClientSQL = get_sogo6_database(process_settings)
        self.crypto = MfaCrypto(process_settings)

    # ----- Settings -------------------------------------------------------

    def allowed_methods(self) -> list[str]:
        """
        Methods the user can use. Empty list = MFA off.
        MFA only applies to plain login (SSO relies on the identity provider).
        Unknown/unregistered ids are ignored.
        """
        settings = self.auth_settings
        if settings is None:
            return []
        if getattr(settings, "SOGO_D_AUTH_TYPE", "plain") != "plain":
            return []
        if not getattr(settings, "SOGO_D_LOGIN_MFA", False):
            return []
        methods: list[str] = getattr(settings, "SOGO_D_LOGIN_MFA_METHOD", []) or []
        return [m for m in methods if get_provider_class(m) is not None]

    def is_enforced(self) -> bool:
        """
        True if every user must have a method
        """
        return bool(self.allowed_methods()) and bool(getattr(self.auth_settings, "SOGO_D_LOGIN_MFA_FORCE", False))

    # ----- Storage of the user's method (column mfa_method) ---------------

    def get_method(self, uid: str) -> dict:
        """
        Return the stored method of the user, {} if none.
        Only place that reads the column (jsonb on PostgreSQL, text on MariaDB).

        :raises RequestException: no user profile for this uid
        """
        self.sogo_db_manager.connect()
        condition = EqualCondition(tbl.COL_USER_UID.name, uid)
        result = list(self.sogo_db_manager.select_from_table(table=tbl.TABLE_USER,
                                                             columns=[tbl.COL_USER_MFA_METHOD],
                                                             condition=condition))
        if len(result) == 0:
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)
        if len(result) > 1:
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        value: Any = result[0][0]
        if not value:
            return {}
        if isinstance(value, str):
            try:
                value = js_loads(value)
            except JSONDecodeError as e:
                raise BugException(f"Column {tbl.COL_USER_MFA_METHOD.name} of {uid} is not a json") from e
        if not isinstance(value, dict):
            raise BugException(f"Column {tbl.COL_USER_MFA_METHOD.name} of {uid} is not a dict")
        return value

    def _set_method(self, uid: str, method: dict | None) -> None:
        """
        Write (or clear with None) the method of the user. Only place that writes the column.

        :raises RequestException: no user profile for this uid
        """
        self.sogo_db_manager.connect()
        condition = EqualCondition(tbl.COL_USER_UID.name, uid)
        row_updated = self.sogo_db_manager.update_in_table(table_name=tbl.TABLE_USER.name,
                                                           column_tuple=(tbl.COL_USER_MFA_METHOD.name,),
                                                           values_list=[method],
                                                           condition=condition)
        if row_updated == 0:
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)
        if row_updated > 1:
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

    def get_active_method(self, uid: str) -> dict:
        """
        Return the method of the user if it is still allowed, {} otherwise.
        A method removed from the allowed methods counts as no method.
        """
        method = self.get_method(uid)
        if method.get("provider") in self.allowed_methods():
            return method
        return {}

    def resolve(self, uid: str) -> MfaDecision:
        """
        Work out what the login must do for this user
        """
        allowed = self.allowed_methods()
        if not allowed:
            return MfaDecision(MFA_ACTION_NONE)
        method = self.get_active_method(uid)
        if method:
            return MfaDecision(MFA_ACTION_VERIFY, provider=method["provider"], method=method, allowed_methods=allowed)
        if self.is_enforced():
            return MfaDecision(MFA_ACTION_ENROLL, allowed_methods=allowed)
        return MfaDecision(MFA_ACTION_NONE)

    def get_status(self, uid: str) -> dict:
        """
        MFA state for the preferences screen. Never returns the secret.
        """
        return self._status(self.get_active_method(uid))

    def _status(self, method: dict) -> dict:
        allowed = self.allowed_methods()
        return {
            "enabled": bool(allowed),
            "enforced": self.is_enforced(),
            "allowed_methods": allowed,
            "method": {
                "provider": method["provider"],
                "created_at": method.get("created_at"),
                "last_used_at": method.get("last_used_at"),
            } if method else None,
        }

    # ----- Helpers --------------------------------------------------------

    @contextmanager
    def _cache(self) -> Iterator[ClientRedis]:
        cache = sogo_cache()
        try:
            yield cache
        finally:
            cache.close()

    def _get_provider(self, ctx: MfaContext, provider_id: str | None, cache: ClientRedis) -> MfaProvider:
        """
        Instantiate an allowed provider

        :raises RequestException: provider unknown or not allowed for the domain
        """
        provider_class = get_provider_class(provider_id or "")
        if provider_class is None or provider_id not in self.allowed_methods():
            raise RequestException(err.ERROR_MFA_METHOD_NOT_ALLOWED.m, err.ERROR_MFA_METHOD_NOT_ALLOWED)
        return provider_class(ctx, cache, self.crypto)

    def _check_rate_limit(self, cache: ClientRedis, uid: str, ip: str | None) -> None:
        """
        :raises RequestException: too many failed codes for this user or this IP
        """
        counters = [(f"{cs.MFA_RL_USER_PREFIX}{uid}", cs.MFA_RL_USER_MAX)]
        if ip:
            counters.append((f"{cs.MFA_RL_IP_PREFIX}{ip}", cs.MFA_RL_IP_MAX))
        for key, max_failures in counters:
            value = cache.get(key, str)
            if value is not None and int(str(value)) >= max_failures:
                logger_mfa.warning("event=rate_limited uid=%s ip=%s", uid, ip)
                raise RequestException(err.ERROR_MFA_TOO_MANY_ATTEMPTS.m, err.ERROR_MFA_TOO_MANY_ATTEMPTS)

    def _register_failure(self, cache: ClientRedis, uid: str, ip: str | None) -> None:
        cache.incr(f"{cs.MFA_RL_USER_PREFIX}{uid}", cs.MFA_RL_WINDOW)
        if ip:
            cache.incr(f"{cs.MFA_RL_IP_PREFIX}{ip}", cs.MFA_RL_WINDOW)

    def _choose_provider_id(self, provider_id: str | None) -> str:
        allowed = self.allowed_methods()
        if not allowed:
            raise RequestException(err.ERROR_MFA_DISABLED.m, err.ERROR_MFA_DISABLED)
        if not provider_id:
            if len(allowed) > 1:
                raise RequestException(err.ERROR_MFA_PROVIDER_REQUIRED.m, err.ERROR_MFA_PROVIDER_REQUIRED)
            return allowed[0]
        if provider_id not in allowed:
            raise RequestException(err.ERROR_MFA_METHOD_NOT_ALLOWED.m, err.ERROR_MFA_METHOD_NOT_ALLOWED)
        return provider_id

    def _check_session_attempts(self, mfa_session: MfaSession | None) -> None:
        """
        Count a failed code on the MFA session, delete it at the last allowed attempt.

        :raises RequestException: the session reached the max number of attempts
        """
        if mfa_session is None:
            return
        voucher_service = VoucherMfaService(self.process_settings)
        attempts = voucher_service.register_failure(mfa_session)
        if attempts >= cs.MFA_MAX_ATTEMPTS:
            voucher_service.delete(mfa_session)
            logger_mfa.warning("event=mfa_session_killed uid=%s attempts=%s", mfa_session.uid, attempts)
            raise RequestException(err.ERROR_MFA_TOO_MANY_ATTEMPTS.m, err.ERROR_MFA_TOO_MANY_ATTEMPTS)

    # ----- Enrollment -----------------------------------------------------

    def begin_enrollment(self, ctx: MfaContext, provider_id: str | None = None,
                         current_code: str | None = None, ip: str | None = None) -> dict:
        """
        Start the setup of a method (e.g. TOTP: new secret + otpauth URI).
        Nothing is written to the profile: the pending enrollment lives in the cache.
        Calling it again replaces the pending enrollment.

        If the user already has an active method, its current code is required to replace it,
        so a stolen session can't replace the victim's MFA.

        :param ctx: user context
        :type ctx: MfaContext
        :param provider_id: method chosen by the user, required if several are allowed
        :type provider_id: str | None
        :param current_code: code of the current method, required if the user has one
        :type current_code: str | None
        :param ip: client IP, for rate limiting and audit
        :type ip: str | None
        :raises RequestException: MFA disabled, method not allowed, code missing/invalid, rate limited
        :return: data for the user (TOTP: provider, otpauth_uri, secret)
        :rtype: dict
        """
        provider_id = self._choose_provider_id(provider_id)
        with self._cache() as cache:
            active = self.get_active_method(ctx.uid)
            if active:
                if not current_code:
                    raise RequestException(err.ERROR_MFA_CODE_REQUIRED.m, err.ERROR_MFA_CODE_REQUIRED)
                self._check_rate_limit(cache, ctx.uid, ip)
                current_provider = self._get_provider(ctx, active["provider"], cache)
                if not current_provider.verify(active, {}, current_code):
                    self._register_failure(cache, ctx.uid, ip)
                    logger_mfa.warning("event=replace_code_failed uid=%s ip=%s provider=%s", ctx.uid, ip, active["provider"])
                    raise RequestException(err.ERROR_MFA_CODE_INVALID.m, err.ERROR_MFA_CODE_INVALID)

            provider = self._get_provider(ctx, provider_id, cache)
            public, pending = provider.begin_enrollment()
            cache.set(f"{cs.MFA_ENROLL_PREFIX}{ctx.uid}", pending, cs.TTL_MFA_ENROLL)

        logger_mfa.info("event=enrollment_started uid=%s ip=%s provider=%s", ctx.uid, ip, provider_id)
        return public

    def confirm_enrollment(self, ctx: MfaContext, code: str, ip: str | None = None,
                           mfa_session: MfaSession | None = None) -> dict:
        """
        Check one code against the pending enrollment, then save the method in the profile
        (replacing the previous one if any).

        :param ctx: user context
        :type ctx: MfaContext
        :param code: code given by the user
        :type code: str
        :param ip: client IP, for rate limiting and audit
        :type ip: str | None
        :param mfa_session: MFA session at stage enroll, if the user is in the forced enrollment
        :type mfa_session: MfaSession | None
        :raises RequestException: no pending enrollment, wrong code, rate limited
        :return: the new MFA status
        :rtype: dict
        """
        enroll_key = f"{cs.MFA_ENROLL_PREFIX}{ctx.uid}"
        with self._cache() as cache:
            self._check_rate_limit(cache, ctx.uid, ip)
            pending = cache.get(enroll_key, dict)
            if not pending or not isinstance(pending, dict):
                raise RequestException(err.ERROR_MFA_NO_PENDING_ENROLLMENT.m, err.ERROR_MFA_NO_PENDING_ENROLLMENT)

            provider = self._get_provider(ctx, pending.get("provider"), cache)
            method = provider.confirm_enrollment(pending, code)
            if method is None:
                self._register_failure(cache, ctx.uid, ip)
                logger_mfa.warning("event=enrollment_code_failed uid=%s ip=%s provider=%s", ctx.uid, ip, provider.id)
                self._check_session_attempts(mfa_session)
                raise RequestException(err.ERROR_MFA_CODE_INVALID.m, err.ERROR_MFA_CODE_INVALID)

            now = _now_iso()
            method["created_at"] = now
            method["last_used_at"] = now
            self._set_method(ctx.uid, method)
            cache.delete(enroll_key)

        logger_mfa.info("event=enrollment_confirmed uid=%s ip=%s provider=%s", ctx.uid, ip, method["provider"])
        return self._status(method)

    def disable(self, ctx: MfaContext, code: str, ip: str | None = None) -> None:
        """
        Remove the method of the user. Requires a valid current code. Refused if MFA is enforced.

        :raises RequestException: enforced, no method, wrong code, rate limited
        """
        if self.is_enforced():
            raise RequestException(err.ERROR_MFA_ENFORCED.m, err.ERROR_MFA_ENFORCED)
        method = self.get_active_method(ctx.uid)
        if not method:
            raise RequestException(err.ERROR_MFA_NOT_SET.m, err.ERROR_MFA_NOT_SET)

        with self._cache() as cache:
            self._check_rate_limit(cache, ctx.uid, ip)
            provider = self._get_provider(ctx, method["provider"], cache)
            if not provider.verify(method, {}, code):
                self._register_failure(cache, ctx.uid, ip)
                logger_mfa.warning("event=disable_code_failed uid=%s ip=%s provider=%s", ctx.uid, ip, method["provider"])
                raise RequestException(err.ERROR_MFA_CODE_INVALID.m, err.ERROR_MFA_CODE_INVALID)

        self._set_method(ctx.uid, None)
        logger_mfa.info("event=disabled uid=%s ip=%s provider=%s", ctx.uid, ip, method["provider"])

    def admin_reset(self, uid: str) -> bool:
        """
        Clear the method of a user (lost device) and its pending enrollment.

        :raises RequestException: no user profile for this uid
        :return: True if the user had a method
        :rtype: bool
        """
        had_method = bool(self.get_method(uid))
        self._set_method(uid, None)
        with self._cache() as cache:
            cache.delete(f"{cs.MFA_ENROLL_PREFIX}{uid}")
        logger_mfa.info("event=admin_reset uid=%s had_method=%s", uid, had_method)
        return had_method

    # ----- Login ----------------------------------------------------------

    def start_login(self, user: User, ip: str | None = None) -> dict | None:
        """
        Called after a valid password.

        :param user: user authenticated by password
        :type user: User
        :param ip: client IP, for audit
        :type ip: str | None
        :return: None if no second factor is needed (the caller issues the user session),
                 otherwise the response with the MFA voucher
        :rtype: dict | None
        """
        decision = self.resolve(user.uid)
        if decision.action == MFA_ACTION_NONE:
            return None

        voucher_service = VoucherMfaService(self.process_settings)
        if decision.action == MFA_ACTION_VERIFY:
            ctx = MfaContext(uid=user.uid, mail=user.mail, auth_settings=self.auth_settings)
            with self._cache() as cache:
                provider = self._get_provider(ctx, decision.provider, cache)
                challenge = provider.start_challenge(decision.method)
            token = voucher_service.create(user, cs.MFA_STAGE_VERIFY, provider=decision.provider, challenge=challenge)
            logger_mfa.info("event=challenge_started uid=%s ip=%s provider=%s", user.uid, ip, decision.provider)
            return {"mfa_required": True, "provider": decision.provider, "mfa_token": token}

        token = voucher_service.create(user, cs.MFA_STAGE_ENROLL, allowed_methods=decision.allowed_methods)
        logger_mfa.info("event=enrollment_required uid=%s ip=%s", user.uid, ip)
        return {"enrollment_required": True, "allowed_methods": decision.allowed_methods, "mfa_token": token}

    def verify_login(self, mfa_session: MfaSession, code: str, ip: str | None = None) -> User:
        """
        Check the code of the MFA session (stage verify). On success the MFA session is consumed.
        At the MFA_MAX_ATTEMPTS-th failure the MFA session is deleted: the user must log in again.

        :raises RequestException: invalid session, wrong code, too many attempts
        :return: the user to create the user session for
        :rtype: User
        """
        if mfa_session.stage != cs.MFA_STAGE_VERIFY:
            raise RequestException(err.ERROR_MFA_SESSION_INVALID.m, err.ERROR_MFA_SESSION_INVALID)

        voucher_service = VoucherMfaService(self.process_settings)
        ctx = MfaContext(uid=mfa_session.uid, mail=mfa_session.mail, auth_settings=self.auth_settings)
        with self._cache() as cache:
            self._check_rate_limit(cache, ctx.uid, ip)
            method = self.get_active_method(ctx.uid)
            if not method or method.get("provider") != mfa_session.provider:
                #The method was reset/changed or is no longer allowed since the password check
                voucher_service.delete(mfa_session)
                raise RequestException(err.ERROR_MFA_SESSION_INVALID.m, err.ERROR_MFA_SESSION_INVALID)

            provider = self._get_provider(ctx, mfa_session.provider, cache)
            if not provider.verify(method, mfa_session.challenge, code):
                self._register_failure(cache, ctx.uid, ip)
                logger_mfa.warning("event=login_code_failed uid=%s ip=%s provider=%s", ctx.uid, ip, mfa_session.provider)
                self._check_session_attempts(mfa_session)
                raise RequestException(err.ERROR_MFA_CODE_INVALID.m, err.ERROR_MFA_CODE_INVALID)

        user = voucher_service.consume(mfa_session)
        method["last_used_at"] = _now_iso()
        self._set_method(ctx.uid, method)
        logger_mfa.info("event=login_success uid=%s ip=%s provider=%s", ctx.uid, ip, mfa_session.provider)
        return user

    def finish_enrollment_login(self, mfa_session: MfaSession) -> dict:
        """
        After a confirmed forced enrollment: the code just checked is the second factor,
        so the MFA session is consumed and the user session issued.

        :raises RequestException: the MFA session is gone
        :return: {"jwt_token": ...}
        :rtype: dict
        """
        user = VoucherMfaService(self.process_settings).consume(mfa_session)
        logger_mfa.info("event=login_success_after_enrollment uid=%s", user.uid)
        return self.issue_user_voucher(user)

    def issue_user_voucher(self, user: User) -> dict:
        """
        Create the user session and its voucher
        """
        voucher_data = VoucherUserService(self.process_settings).generate_voucher_from_user(user)
        return {"jwt_token": voucher_data}
