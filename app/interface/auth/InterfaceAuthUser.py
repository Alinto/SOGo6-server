from __future__ import annotations
from typing import TYPE_CHECKING, Any

from app.config.settings.SystemSettings import SystemSettingsObj
from app.config.settings.DomainSettings import AuthSettingsObj, UserSourceSettingsObj
from app.module.auth.ModuleAuth import ModuleAuth
from app.module.auth.ModuleUserSource import ModuleUserSource
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceAuthUser:
    """
    Interface for user authentication
    """

    def __init__(self, process: ProcessSetting, system: dict, default_domain: dict):
        system_settings = SystemSettingsObj(system["SYSTEM_SETTINGS"])
        default_auth = AuthSettingsObj(default_domain["AUTH_SETTINGS"])


        default_us_source_raw: dict = default_domain["USER_SOURCE"]
        default_us_source: dict = {}
        for source_uid, source_settings in default_us_source_raw.items():
            default_us_source[source_uid] = UserSourceSettingsObj(source_settings)

        self.module_auth = ModuleAuth(process, system_settings, default_auth, default_us_source)
        self.module_user_source = ModuleUserSource(default_us_source)
        self.module_user_profile = ModuleUserProfile(process, default_domain)



    def get_login_mech(self, user_uid:str, redirect:str) -> tuple[dict, int]:
        """
        Get the login mech from a uid

        :param user_uid: _description_
        :type user_uid: str
        :return: _description_
        :rtype: tuple[dict, int]
        """
        try:
            ret = self.module_auth.get_login_mech(user_uid)
        except RequestException as e:
            return create_api_base_response(str(e), e.error_code), 400
        return create_api_base_response(ret), 200

    def plain_login(self, data:dict) -> tuple[dict, int]:
        """
        Check a plain login uid/password.


        :param data: _description_
        :type data: dict
        :return: _description_
        :rtype: tuple[dict, str, int]
        """
        uid = data["username"]
        password = data["password"]

        success, ret = self.module_auth.user_plain_login(uid, password)
        if not success:
            return create_api_base_response(), 401

        try:
            self.module_user_profile
            if not self.module_user_profile.is_user_profile_present(uid):
                contact_info = self.module_user_source.get_contact_info(uid)
                self.module_user_profile.create_user_profile(uid, contact_info)
        except RequestException as ex:
            logger_api.error("Request exception when onboarding user %s: %s", uid, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception when onboarding user %s: %s", uid, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

        return create_api_base_response(ret), 200
