from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.user.InterfaceUserProfile import InterfaceUserProfile
from app.utils.logger.logger import logger_api

from .schema import userPreferences as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.pagin_sort_filter import FakePaginationParameters
    from app.auth.User import User



blp = Blueprint("Profile", __name__, url_prefix="/profile")


@blp.before_request
def init_user_profile() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiUserPreferences")
    process: ProcessSetting = g.process
    system_settings: dict = g.system_settings
    user_domain: dict = g.user_domain
    user: User = g.user
    interface_api = InterfaceUserProfile(process_settings=process, user_domain=user_domain, user=user)
    g.inter = interface_api

@blp.route("")
class ApiUserProfile(MethodView):
    """
    Return all the info of the user after a successfull login
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Collection, return all user preferences
        """
        interface_api : InterfaceUserProfile = g.inter
        return interface_api.get_user_profile()


