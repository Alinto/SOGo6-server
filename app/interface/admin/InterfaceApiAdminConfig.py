from __future__ import annotations
from typing import TYPE_CHECKING, Any

from marshmallow.exceptions import ValidationError

from app.config.db import tables as tbl
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.db.Condition import Order, order_str_to_order_enum
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

    def get_dynamic_setting_structure(self) -> dict:
        """
        Return the dynamic table
        """
        ret = self.module.get_dynamic_form_settings()
        return create_api_base_response(ret)


    def get_all_setting_system(self) -> dict:
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
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        return create_api_base_response(ret_values), 200

    def get_all_setting_domain_default(self) -> dict:
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
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        return create_api_base_response(ret_values), 200


    def get_all_domain_settings(self, first_item: int = 0, last_item: int = 20, sort: str = "", order_str: str = "") -> tuple[int, dict, int]:
        """
        Fetch all domains according to pagination params, order and sorting

        :param first_item: Index of the first item to retrieve, defaults to 0
        :type first_item: int
        :param last_item: Index of the last item to retrieve, defaults to 20
        :type last_item: int
        :param sort: Column name to sort by, defaults to ""
        :type sort: str
        :param order_str: Sort direction ("asc" or "desc"), defaults to ""
        :type order_str: str
        :return: Tuple containing total count, API response dict, and HTTP status code
        :rtype: tuple[int, dict, int]
        """
        offset = first_item
        limit = last_item - first_item + 1

        if order_str:
            try:
                order = order_str_to_order_enum(order_str)
            except BugException as exc:
                return 0, create_api_base_response(str(exc), err.ERROR_BUG_UNKNWON_ORDER), 400 #TODO: 500?
        else:
            order = Order.ASC

        if sort:
            try:
                sort_by = tbl.TABLE_DOMAIN.get_column_from_name(sort)
            except RequestException as exc:
                return 0, create_api_base_response(str(exc), exc.error_code), 400
        else:
            sort_by = None

        count, ret = self.module.get_all_domains_settings(offset=offset, limit=limit, sort_by=sort_by, order=order)
        return  count, create_api_base_response(ret), 200

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
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 400
        return create_api_base_response(ret_values), 200

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
            return create_api_base_response(str(ex), ex.error_code), 404
        return create_api_base_response(ret_values), 200

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
            return create_api_base_response(str(ex), ex.error_code), 404
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        return create_api_base_response(ret_values), 200

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
            return create_api_base_response(str(ex), ex.error_code), 404
        return {}, 200
