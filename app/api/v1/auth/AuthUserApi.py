from __future__ import annotations
from typing import TYPE_CHECKING

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
    from app.utils.api.pagin_sort_filter import FakePaginationParameters



blp = Blueprint("ApiConfig", __name__, url_prefix="/auth")


@blp.before_request
def init_admin_config() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiAdminConfig")
    process: ProcessSetting = g.process
    system: dict = g.system
    default_domain: dict = g.default_domain
    system_settings = SystemSettingsObj(system["SYSTEM_SETTINGS"])
    interface_api = InterfaceAuthUser(process, system_settings, default_domain)
    g.inter = interface_api




@blp.route("/login")
class ApiAuthUser(MethodView):
    """
    Action

    Endpoint that return the dynamic settings structure
    """
    @blp.arguments(sch.AuthUserGetMechSchema, location='query', error_status_code=400)
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Action, return the url location of the login system for this user
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_dynamic_setting_structure()

    @blp.arguments(sch.AuthUserBasicPostShhema, error_status_code=400)
    @blp.response(200)
    def post(self, new_data:dict) -> ResponseReturnValue:
        """
        Action, Authenticate the user
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_dynamic_setting_structure()
