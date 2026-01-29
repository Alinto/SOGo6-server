from __future__ import annotations
from typing import TYPE_CHECKING, cast

from marshmallow import EXCLUDE, ValidationError

from app.config.db import tables as tbl
from app.config.settings.DomainSettings import get_all_domain_schemas
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import BugException, RequestException
from app.utils import errors as err



if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User
    

class InterfaceUserProfile:
    """
    Interface for user profile
    """
    
    def __init__(self, process_settings: ProcessSetting, user_domain: dict, user: User):
        self.process_settings = process_settings
        self.user = user
        self.user_domain = user_domain
        self.module_user_profile = ModuleUserProfile(process_settings, user_domain)
    
    def get_user_profile(self) -> tuple[dict, int]:
        """
        User profile is:
        - user accounts
        - user preferences
        - user Folder view (NOT IMPLEMENTED)
        - admin param for UI

        It is called by the UI to know how the UI must be handled

        :return: 
        :rtype: tuple[dict, int]
        """
        data: dict = {}

        #User accounts
        try:
            data["mailboxes"] = self.module_user_profile.list_accounts(self.user)
        except RequestException as ex:
            return create_api_base_response(None, ex.error_code), ex.http_status

        #User preferences
        try:
            data["prefs"] = self.module_user_profile.get_user_preferences(self.user.uid)
        except RequestException as e:
            return create_api_base_response(error=e.error_code), e.http_status
        
        #TODO User folders view (NOT IMPLEMENTED)
        
        #Admin param
        admin_param: dict = {}
        for domain_schema in get_all_domain_schemas():
            subparent = domain_schema.subparent
            domain_sub: dict = self.user_domain[subparent]
            for setting_needed in domain_schema.is_needed_by_ui:
                admin_param[setting_needed] = domain_sub.get(setting_needed, None)
        data["ui"] = admin_param

        return create_api_base_response(data), 200

