from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.service import sogo_cache
from app.interface.user.InterfaceUserPreferences import InterfaceUserPreferences
from app.utils.logger.logger import logger_api

from .schema import userPreferences as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.pagin_sort_filter import FakePaginationParameters
    from app.auth.User import User



blp = Blueprint("Preferences", __name__, url_prefix="/preferences")


@blp.before_request
def init_user_profile() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiUserPreferences")
    process: ProcessSetting = g.process_settings
    system_settings: dict = g.system_settings
    default_domain: dict = g.default_domain_settings
    user: User = g.user
    interface_api = InterfaceUserPreferences(process_settings=process, default_domain=default_domain, user=user)
    g.inter = interface_api

@blp.route("")
class ApiUserPreferences(MethodView):
    """
    Collection
    """
    @blp.response(200, schema=sch.UserPeferencesGetRetSchema, example=sch.UserPeferencesGetRetSchema.example())
    def get(self) -> ResponseReturnValue:
        """
        Collection, return all user preferences
        """
        interface_api : InterfaceUserPreferences = g.inter
        return interface_api.get_all_preferences()

    @blp.arguments(sch.UserPreferencesPatch, example=sch.UserPreferencesPatch.example(), error_status_code=400)
    @blp.response(200, schema=sch.UserPeferencesGetRetSchema, example=sch.UserPeferencesGetRetSchema.example())
    def patch(self, new_data:dict)-> ResponseReturnValue:
        """
        Collection, modify all user preferences
        """
        interface_api : InterfaceUserPreferences = g.inter
        return interface_api.update_all_preferences(new_data["settings"])


# @blp.route("/<string:pref_type>")
# class ApiUserPreferencesPart(MethodView):
#     """
#     Resource,
#     """
#     @blp.response(200)
#     def get(self, pref_type:str) -> ResponseReturnValue:
#         """
#         Resource, fetch the system settings
#         """
#         interface_api : InterfaceUserPreferences = g.inter
#         return interface_api.get_partial_preferences(pref_type)

#     #@blp.arguments(sch.AdminConfigSystemPatchSchema, example=sch.AdminConfigSystemPatchSchema.example(), error_status_code=400)
#     @blp.response(200)
#     def patch(self, new_data: dict, pref_type:str) -> ResponseReturnValue:
#         """
#         Resource, update the system settings
#         """
#         interface_api : InterfaceUserPreferences = g.inter
#         return interface_api.update_partial_preferences(new_data, pref_type)

