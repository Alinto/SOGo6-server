from __future__ import annotations
from typing import TYPE_CHECKING, cast

from flask import g, request, url_for, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.config.settings.SystemSettings import SystemSettingsObj
from app.interface.auth.InterfaceAuthUser import InterfaceAuthUser
from app.utils.logger.logger import logger_api

from .schema import authUser as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


blp = Blueprint("Auth", __name__, url_prefix="/auth")

#Endpoint of the SSO callback, by SOGO_D_AUTH_TYPE
SSO_CALLBACK_ENDPOINTS = {
    "openid": ".ApiAuthUserCallbackOpenid",
}


def build_sso_callback_url(kind:str, domain:str) -> str:
    """
    Return the full url of the SSO callback for this kind and domain.
    This is the redirect_uri given to the identity provider.

    :param kind: SOGO_D_AUTH_TYPE of the domain
    :type kind: str
    :param domain: Domain of the user
    :type domain: str
    :return: The callback url, empty if this kind has no callback (plain)
    :rtype: str
    """
    endpoint = SSO_CALLBACK_ENDPOINTS.get(kind)
    if endpoint is None:
        return ""
    return url_for(endpoint, domain=domain, _external=True)


@blp.before_request
def init_admin_config() -> None:
    """
    Init the interface and others if needed 
    """
    logger_api.debug("Calling before_request for ApiAdminConfig")
    process: ProcessSetting = g.process_settings
    system_settings: dict = g.system_settings
    default_domain: dict = g.default_domain_settings
    interface_api = InterfaceAuthUser(process, system_settings, default_domain)
    g.inter = interface_api


@blp.route("/mode")
class ApiAuthUserMode(MethodView):
    """
    Action

    Return the authnetication mode for this user
    """
    @blp.arguments(sch.AuthUserGetMechSchema, location='query', as_kwargs=True, error_status_code=400)
    @blp.response(200)
    def get(self, username:str, redirect:str) -> ResponseReturnValue:
        """
        Action, return the url location of the login system for this username.
        redirect is only useful for SSO that needs callback.
        """
        interface_api: InterfaceAuthUser = g.inter
        return interface_api.get_login_mech(username, redirect, build_sso_callback_url)


@blp.route("/login")
class ApiAuthUserLogin(MethodView):
    """
    Action, plain login for user
    """

    @blp.arguments(sch.AuthUserBasicPostSchema, example=sch.AuthUserBasicPostSchema.example(), error_status_code=400)
    @blp.response(200)
    def post(self, new_data:dict) -> ResponseReturnValue:
        """
        Action, Authenticate the user for plain mode
        """
        interface_api : InterfaceAuthUser = g.inter
        return interface_api.plain_login(new_data)


@blp.route("/callback/openid/<string:domain>")
class ApiAuthUserCallbackOpenid(MethodView):
    """
    Action, is the callback for openid SSO
    """

    @blp.response(200)
    def get(self, domain:str) -> ResponseReturnValue:
        """
        Action, Callback for this domain when doing openid SSO.
        The query parameters are given by the openid server (code, or error and error_description)
        """
        interface_api : InterfaceAuthUser = g.inter
        return interface_api.sso_callback("openid", domain, request.args.to_dict(), build_sso_callback_url)


@blp.route("/logout")
class ApiAuthUserLogout(MethodView):
    """
    Action, revoke the current user session
    """

    @blp.response(200)
    def post(self) -> ResponseReturnValue:
        """
        Action, logout the authenticated user by revoking the session associated
        with the JWT token present in the Authorization header.
        """
        auth_header = request.authorization
        voucher_data: str = ""
        if auth_header and auth_header.token:
            voucher_data = auth_header.token
        interface_api: InterfaceAuthUser = g.inter
        return interface_api.logout(voucher_data)
