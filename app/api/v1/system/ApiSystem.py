from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.service import sogo_cache
from app.interface.system.InterfaceSystem import InterfaceSystem
from app.utils.logger.logger import logger_api

from .schema import system as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User



blp = Blueprint("System", __name__, url_prefix="/system")


@blp.before_request
def init_user_profile() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiSystem")
    system_settings: dict = g.system_settings
    default_domain: dict = g.default_domain_settings
    interface_api = InterfaceSystem(system_settings=system_settings, default_domain=default_domain)
    g.inter = interface_api

@blp.route("")
class ApiSystem(MethodView):
    """
    SIngleton, return the system parameters needed by UI before the user login
    """
    @blp.response(200, schema=sch.SystemGetRetSchema, example=sch.SystemGetRetSchema.example())
    def get(self) -> ResponseReturnValue:
        """
        Collection, return all user preferences
        """
        interface_api : InterfaceSystem = g.inter
        return interface_api.get_ui_system_param()
