from __future__ import annotations
from typing import TYPE_CHECKING

from marshmallow.exceptions import ValidationError

from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException, BugException
from app.utils import errors as err

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

class InterfaceApiAdminConfig:
    """
    Interface for the api ApiAdminConfig
    """
    def __init__(self, process_setting: ProcessSetting) -> None:
        """
        This interface only needs to know the process settings and the user

        :param process_settings: the process settings
        :type process_settings: ProcessSetting
        """
        self.module = ModuleAdminConfig(process_settings=process_setting)

    def get_dynamic_setting_structure(self) -> tuple[dict, int]:
        """
        Return the dynamic table
        """
        ret = self.module.get_dynamic_form_settings()
        return create_api_base_response(ret)


    def get_all_setting_system(self) -> tuple[dict, int]:
        """
        Return the system setting
        """
        ret = self.module.get_system_settings()
        return create_api_base_response(ret)

    def update_all_setting_system(self, new_param: dict) -> tuple[dict, int]:
        """
        Update the system settings

        :param new_param: new parameters
        :type new_param: dict
        :return: Two keys: the value to send back and the status code
        the second key `errors` is a string with the readable error
        :rtype: dict
        """
        try:
            _, ret_values = self.module.update_system_settings(new_param)
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR)
        return create_api_base_response(ret_values)

    def get_all_setting_domain_default(self) -> tuple[dict, int]:
        """
        Return the default settings for all domains
        """
        ret = self.module.get_default_domain_settings()
        return create_api_base_response(ret)

    def update_all_setting_domain_default(self, new_param: dict) -> tuple[dict, int]:
        """
        Update the domain default settings

        :param new_param: new parameters
        :type new_param: dict
        :return: Two keys: `status` a bool to say if the update has been ok. If False,
        the second key `errors` is a string with the readable error
        :rtype: dict
        """
        try:
            _, ret_values = self.module.update_domain_default_settings(new_param)
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR)
        return create_api_base_response(ret_values)


    def get_all_domain_settings(self, first_item: int = 0, last_item: int = 20,
                                sort_args: dict | None = None,
                                fields_args: dict | None = None) -> tuple[int, dict, int]:
        """
        Return the list of all domains settings with pagination, sorting and filtering options
        """
        offset = first_item
        limit = last_item - first_item + 1
        try:
            count, ret = self.module.get_all_domains_settings(
                offset=offset,
                limit=limit,
                include_fields=fields_args.get("include_fields") if fields_args else None,
                sort_by=sort_args.get("sort_by") if sort_args else None,
                sort_order=sort_args.get("sort_order", "asc") if sort_args else "asc",
            )
        except RequestException as ex:
            response, status_code = create_api_base_response(str(ex), ex.error)
            return 0, response, status_code
        except BugException as ex:
            response, status_code = create_api_base_response(str(ex), err.ERROR_BUG_UNKNWON_COLUMN)
            return 0, response, status_code
        response, status_code = create_api_base_response(ret)
        return count, response, status_code


    def post_new_domain_settings(self, new_domain: dict) ->tuple[dict, int]:
        """
        Create a new set of settings for a domain

        :param new_domain: Dictionary containing domain configuration (domain_name, domain_description, domain_info, settings)
        :type new_domain: dict
        :return: Tuple containing API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """

        try:
            _, ret_values = self.module.create_domain_settings(new_domain)
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR)
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error)
        return create_api_base_response(ret_values)

    def get_domain_settings(self, domain_id: str) -> tuple[dict, int]:
        """
        Get domain settings for a domain

        :param domain_id: The domain name/ID
        :type domain_id: str
        :return: Tuple containing API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """

        try:
            ret_values = self.module.get_one_domain_setting(domain_id)
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error)
        return create_api_base_response(ret_values)

    def update_domain_settings(self, domain_id: str, new_data: dict) -> tuple[dict, int]:
        """
        Update one domain settings

        :param domain_id: The domain name/ID
        :type domain_id: str
        :param new_data: Dictionary containing updated domain configuration (JSON merge patch format)
        :type new_data: dict
        :return: Tuple containing API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            _, ret_values = self.module.update_one_domain_settings(domain_id, new_data)
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error)
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR)
        return create_api_base_response(ret_values)

    def delete_domain_settings(self, domain_id: str) -> tuple[dict, int]:
        """
        Delete settings for a specific domain

        :param domain_id: The domain name/ID
        :type domain_id: str
        :return: Tuple containing API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            _ = self.module.delete_one_domain_setting(domain_id)
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error)
        return {}, 200
