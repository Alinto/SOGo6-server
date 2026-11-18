from __future__ import annotations
from typing import TYPE_CHECKING

from app.auth.User import UserAnonymous
from app.config.settings.DomainSettings import AuthSettings, AuthSettingsObj
from app.module.auth.mfa.MfaProvider import MfaContext
from app.module.auth.mfa.ModuleMfa import ModuleMfa
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import BugException, RequestException
from app.utils import constants as cs
from app.utils import errors as err

if TYPE_CHECKING:
    from app.auth.User import User
    from app.auth.service.VoucherMfaService import MfaSession
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceUserMfa:
    """
    Interface for the user MFA endpoints (preferences -> security, and forced enrollment).

    The caller is either an authenticated user, or an MFA session at stage enroll
    (the access control in create_app only lets the enroll stage reach POST /mfa and POST /mfa/confirm).
    """

    def __init__(self, process_settings: ProcessSetting, user_domain: dict, user: User,
                 mfa_session: MfaSession | None = None):
        self.process_settings = process_settings
        self.user = user
        self.mfa_session = mfa_session
        auth_settings = AuthSettingsObj(user_domain.get(AuthSettings.subparent, {}))
        self.module_mfa = ModuleMfa(process_settings, auth_settings)

        self.ctx: MfaContext | None = None
        self.enroll_session: MfaSession | None = None
        if user is not None and not isinstance(user, UserAnonymous) and user.authenticated:
            self.ctx = MfaContext(uid=user.uid, mail=user.mail, auth_settings=auth_settings)
        elif mfa_session is not None and mfa_session.stage == cs.MFA_STAGE_ENROLL:
            self.ctx = MfaContext(uid=mfa_session.uid, mail=mfa_session.mail, auth_settings=auth_settings)
            self.enroll_session = mfa_session

    def get_status(self) -> tuple[dict, int]:
        """
        Return the MFA state of the user: allowed methods, enforcement, active method (never the secret)
        """
        if self.ctx is None:
            return create_api_base_response(None, err.ERROR_AUTHENTICATED_ROUTE)
        try:
            ret = self.module_mfa.get_status(self.ctx.uid)
        except (RequestException, BugException) as ex:
            return create_api_base_response(None, ex.error)
        return create_api_base_response(ret)

    def begin_enrollment(self, provider_id: str | None, current_code: str | None, ip: str | None) -> tuple[dict, int, dict]:
        """
        Start the setup of a method. TOTP: returns the otpauth:// URI (to render as a QR code)
        and the secret for manual entry. The response must not be cached.
        """
        no_store = {"Cache-Control": "no-store"}
        if self.ctx is None:
            return *create_api_base_response(None, err.ERROR_AUTHENTICATED_ROUTE), no_store
        try:
            ret = self.module_mfa.begin_enrollment(self.ctx, provider_id, current_code, ip)
        except (RequestException, BugException) as ex:
            return *create_api_base_response(None, ex.error), no_store
        return *create_api_base_response(ret), no_store

    def confirm_enrollment(self, code: str, ip: str | None) -> tuple[dict, int]:
        """
        Save the pending method after one valid code.
        From the forced enrollment (MFA session), the user session is issued right away:
        the code just checked is the second factor.
        """
        if self.ctx is None:
            return create_api_base_response(None, err.ERROR_AUTHENTICATED_ROUTE)
        try:
            status = self.module_mfa.confirm_enrollment(self.ctx, code, ip, self.enroll_session)
            if self.enroll_session is not None:
                return create_api_base_response(self.module_mfa.finish_enrollment_login(self.enroll_session))
        except (RequestException, BugException) as ex:
            return create_api_base_response(None, ex.error)
        return create_api_base_response(status)

    def disable(self, code: str, ip: str | None) -> tuple[dict, int]:
        """
        Remove the method of the user (refused when MFA is enforced)
        """
        if self.ctx is None or self.enroll_session is not None:
            return create_api_base_response(None, err.ERROR_AUTHENTICATED_ROUTE)
        try:
            self.module_mfa.disable(self.ctx, code, ip)
            ret = self.module_mfa.get_status(self.ctx.uid)
        except (RequestException, BugException) as ex:
            return create_api_base_response(None, ex.error)
        return create_api_base_response(ret)
