from __future__ import annotations
from typing import TYPE_CHECKING, cast

from flask import g, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.config.settings.SystemSettings import SystemSettingsObj
from app.interface.auth.InterfaceAuthUser import InterfaceAuthUser
from app.utils.logger.logger import logger_api

from .schema import authUser as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.paginate_sort_filter import FakePaginationParameters


blp = Blueprint("Auth", __name__, url_prefix="/auth")


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

    Return the authneticaiton mode for this user
    """
    @blp.arguments(sch.AuthUserGetMechSchema, location='query', as_kwargs=True, error_status_code=400)
    @blp.response(200)
    def get(self, username:str, redirect:str) -> ResponseReturnValue:
        """
        Action, return the url location of the login system for this username.
        redirect is only useful for SSO that needs callback.
        """
        interface_api: InterfaceAuthUser = g.inter
        return interface_api.get_login_mech(username, redirect)


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


@blp.route("/callback/<string:domain>")
class ApiAuthUserCallback(MethodView):
    """
    Action, is the callback for SSO
    """

    @blp.response(200)
    def get(self, new_data:dict) -> ResponseReturnValue:
        """
        Action, Callback for this domain when doing SSO.
        The query parameters 
        """
        interface_api : InterfaceAuthUser = g.inter
        raise NotImplementedError("Not implemented yet")
