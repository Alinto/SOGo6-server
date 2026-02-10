from __future__ import annotations
from typing import TYPE_CHECKING, cast

from marshmallow import EXCLUDE, ValidationError

from app.config.db import tables as tbl
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import BugException, RequestException
from app.utils import errors as err



if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User


class InterfaceUserPreferences:
    """
    Interface for user profile
    """

    def __init__(self, process_settings: ProcessSetting, user_domain: dict, user: User):
        self.process_settings = process_settings
        self.user = user
        self.domain_settings = user_domain
        self.module_user_profile = ModuleUserProfile(process_settings, user_domain)

    def get_all_preferences(self) -> tuple[dict, int]:
        """
        Retrun the complete profile of a user

        :return: _description_
        :rtype: tuple[dict, int]
        """
        try:
            data = self.module_user_profile.get_user_preferences(self.user.uid)
        except RequestException as e:
            return create_api_base_response(error=e.error_code), e.http_status
        return create_api_base_response(data), 200


    def get_partial_preferences(self, subparent:str) -> tuple[dict, int]:
        """Get partial user preferences for a specific subparent

        :param subparent: The subparent key to retrieve preferences for
        :type subparent: str
        :return: The user preferences for the specified subparent
        :rtype: tuple[dict, int]
        """
        try:
            data = self.module_user_profile.get_partial_user_preferences(self.user.uid, subparent)
        except RequestException as e:
            return create_api_base_response(error=e.error_code), e.http_status
        return create_api_base_response(data), 200

    def update_all_preferences(self, new_data:dict) -> tuple[dict, int]:
        """
        Update all user preferences

        :param new_data: The new data to update
        :type new_data: dict
        :return: The updated user preferences
        :rtype: tuple[dict, int]
        """
        try:
            data = self.module_user_profile.update_user_preferences(self.user.uid, new_data)
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as e:
            return create_api_base_response(error=e.error_code), e.http_status
        return create_api_base_response(data), 200

    def update_partial_preferences(self, new_data:dict, subparent:str) -> tuple[dict, int]:
        """Update partial user preferences for a specific subparent

        :param new_data: The new data to update
        :type new_data: dict
        :param subparent: The subparent key to update preferences for
        :type subparent: str
        :return: The updated user preferences
        :rtype: tuple[dict, int]
        """
        try:
            data = self.module_user_profile.update_user_preferences(self.user.uid, new_data, subparent)
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as e:
            return create_api_base_response(error=e.error_code), e.http_status
        return create_api_base_response(data), 200
