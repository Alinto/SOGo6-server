from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, request
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.user.InterfaceUserMfa import InterfaceUserMfa
from app.utils.logger.logger import logger_api

from .schema import userMfa as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


blp = Blueprint("Mfa", __name__, url_prefix="/mfa")


@blp.before_request
def init_user_mfa() -> None:
    """
    Init the interface. The caller is a user, or an MFA session at stage enroll
    """
    logger_api.debug("Calling before_request for ApiUserMfa")
    process: ProcessSetting = g.process_settings
    g.inter = InterfaceUserMfa(process_settings=process,
                               user_domain=g.user_domain_settings,
                               user=g.user,
                               mfa_session=g.get("mfa_session"))


@blp.route("")
class ApiUserMfa(MethodView):
    """
    Singleton, the MFA method of the user.

    Used by preferences -> security. POST is also reachable with an MFA voucher at stage
    enroll (forced enrollment at login).
    """

    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Singleton, return the MFA state: enabled, enforced, allowed methods and active method
        (provider, created_at, last_used_at). Never returns the secret.
        """
        interface_api: InterfaceUserMfa = g.inter
        return interface_api.get_status()

    @blp.arguments(sch.UserMfaBeginSchema, example=sch.UserMfaBeginSchema.example(), error_status_code=400)
    @blp.response(200)
    def post(self, new_data: dict) -> ResponseReturnValue:
        """
        Singleton, start the setup of a method (the "enable MFA" button).

        `provider` is required if several methods are allowed. If the user already has a method,
        `code` (a code of the current method) is required to replace it.
        TOTP returns `otpauth_uri` (to render as a QR code) and `secret` (manual entry), only once.
        Nothing is saved until POST /mfa/confirm.
        """
        interface_api: InterfaceUserMfa = g.inter
        return interface_api.begin_enrollment(new_data.get("provider"), new_data.get("code"), request.remote_addr)

    @blp.arguments(sch.UserMfaCodeSchema, example=sch.UserMfaCodeSchema.example(), error_status_code=400)
    @blp.response(200)
    def delete(self, new_data: dict) -> ResponseReturnValue:
        """
        Singleton, remove the MFA method. Requires a valid current code. 403 if MFA is enforced.
        """
        interface_api: InterfaceUserMfa = g.inter
        return interface_api.disable(new_data["code"], request.remote_addr)


@blp.route("/confirm")
class ApiUserMfaConfirm(MethodView):
    """
    Action, confirm the pending setup with one valid code
    """

    @blp.arguments(sch.UserMfaCodeSchema, example=sch.UserMfaCodeSchema.example(), error_status_code=400)
    @blp.response(200)
    def post(self, new_data: dict) -> ResponseReturnValue:
        """
        Action, save the method after one valid code (replaces the previous one if any).
        With a user session, returns the new MFA state.
        With an MFA voucher at stage enroll, returns the user voucher (jwt_token).
        """
        interface_api: InterfaceUserMfa = g.inter
        return interface_api.confirm_enrollment(new_data["code"], request.remote_addr)
