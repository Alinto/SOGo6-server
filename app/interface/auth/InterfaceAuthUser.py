from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.settings.SystemSettings import SystemSettingsObj, SystemSettings
from app.config.settings.DomainSettings import AuthSettingsObj, AuthSettings, UserSourceSettings, UserSourceSettingsObj
from app.module.auth.ModuleAuth import ModuleAuth
from app.module.auth.ModuleUserSource import ModuleUserSource
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException, BugException
from app.utils import errors as err
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User, UserAnonymous


class InterfaceAuthUser:
    """
    Interface for user authentication
    """

    def __init__(self, process: ProcessSetting, system: dict, default_domain: dict):
        system_settings = SystemSettingsObj(system[SystemSettings.subparent])
        default_auth = AuthSettingsObj(default_domain[AuthSettings.subparent])

        default_us_source_raw: dict = default_domain[UserSourceSettings.subparent]
        default_us_source: dict = {}
        for source_uid, source_settings in default_us_source_raw.items():
            default_us_source[source_uid] = UserSourceSettingsObj(source_settings)

        self.module_auth = ModuleAuth(process, system_settings, default_auth, default_us_source)
        self.module_user_profile = ModuleUserProfile(process, default_domain)


    def get_login_mech(self, user_uid:str, redirect:str) -> tuple[dict, int]:
        """
        Get the login mech from a uid

        :param user_uid: The user unique ID
        :type user_uid: str
        :param redirect: The redirect URL after authentication
        :type redirect: str
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            ret = self.module_auth.get_login_mech(user_uid)
        except RequestException as e:
            return create_api_base_response(str(e), e.error)
        return create_api_base_response(ret)

    def _check_login(self, uid:str, password:str) -> tuple[bool, User, ModuleUserSource]:
        """
        Check credentials uid/password/token of a user
        #TODO get login auth with AuthSettingsObj

        :param uid: uid of the user
        :type username: str
        :param password: password or token or any equivalent
        :type password: str
        :return: True if success, instante of User, instande of Appropriate ModuleUserSource
        :rtype: tuple[bool, User, ModuleUserSource]
        """
        # Prepare the user object for authentication and get domain user sources
        user, domain_user_sources = self.module_auth.get_user_and_domain_user_sources(uid, password)

        # Check login using the user source module
        module_us = ModuleUserSource(domain_user_sources)
        return module_us.check_login(user), user, module_us

    def plain_login(self, data:dict) -> tuple[dict, int]:
        """
        Check a plain login uid/password.

        :param data: Dictionary containing 'username' and 'password' keys
        :type data: dict
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        uid = data["username"]
        password = data["password"]

        success, user, module_us = self._check_login(uid, password)

        if not success:
            return create_api_base_response(None, err.ERROR_LOGIN_FAILED)

        # Generate the voucher for the authenticated user
        ret = self.module_auth.generate_voucher_from_user(user)

        try:
            if not self.module_user_profile.is_user_profile_present(uid):
                self.module_user_profile.create_user_profile(user)
        except RequestException as ex:
            logger_api.error("Request exception when onboarding user %s: %s", uid, str(ex))
            return create_api_base_response(None, ex.error)

        return create_api_base_response(ret)

    def check_user_and_fill_info(self, user:User) -> bool:
        """
        Directly used by the before_request at init.
        Check that the user credentials is still relevant and fill the user instance with infos needed

        :param user: _description_
        :type user: User
        :return: True if the user credentials are ok
        :rtype: bool
        """
        success, _, module_us = self._check_login(user.uid, user.password)
        if success:
            module_us.fill_user(user)
            self.module_user_profile.get_user_profile(user)
        return success

