from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.service import sogo_cache
from app.interface.profile.InterfaceUserProfile import InterfaceUserProfile
from app.utils.logger.logger import logger_api

from .schema import userProfile as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.pagin_sort_filter import FakePaginationParameters



blp = Blueprint("ApiUserProfile", __name__, url_prefix="/profile")


@blp.before_request
def init_user_profile() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiUserProfile")
    process: ProcessSetting = g.process
    system_settings: dict = g.system_settings
    default_domain: dict = g.default_domain
    interface_api = InterfaceUserProfile(process_setting=process)
    g.inter = interface_api
    sogo_cache().set("test", "banane", 500)

@blp.route("")
class ApiUserProfile(MethodView):
    """
    Collection
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Collection, return all user profile (except account and identities)
        """
        interface_api : InterfaceUserProfile = g.inter
        raise NotImplementedError()

    def patch(self)-> ResponseReturnValue:
        """
        Collection, modify all user profile
        """
        interface_api : InterfaceUserProfile = g.inter
        raise NotImplementedError()


@blp.route("/<string:profile_type>")
class ApiAdminConfigSystem(MethodView):
    """
    Resource,

    Endpoint that return the list of the system settings
    """
    @blp.response(200)
    def get(self,) -> ResponseReturnValue:
        """
        Resource, fetch the system settings
        """
        interface_api : InterfaceUserProfile = g.inter
        raise NotImplementedError()

    #@blp.arguments(sch.AdminConfigSystemPatchSchema, example=sch.AdminConfigSystemPatchSchema.example(), error_status_code=400)
    @blp.response(200)
    def patch(self, new_data: dict) -> ResponseReturnValue:
        """
        Resource, update the system settings
        """
        interface_api : InterfaceUserProfile = g.inter
        raise NotImplementedError()

