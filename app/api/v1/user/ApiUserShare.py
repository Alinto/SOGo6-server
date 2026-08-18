from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.user.InterfaceUserShare import InterfaceUserShare
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User


blp = Blueprint("Share", __name__, url_prefix="/share")


@blp.before_request
def init_user_share() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiUserShare")
    process: ProcessSetting = g.process_settings
    user_domain: dict = g.user_domain_settings
    user: User = g.user
    interface_api = InterfaceUserShare(process_settings=process, user_domain=user_domain, user=user)
    g.inter = interface_api


@blp.route("")
class ApiUserShare(MethodView):
    """
    Return user's shared folders (calendars and addressbooks)
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Get user's folders structure
        """
        interface_api: InterfaceUserShare = g.inter
        return interface_api.get_user_share()
