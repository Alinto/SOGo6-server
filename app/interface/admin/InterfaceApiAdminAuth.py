"""
Interface for admin authentication
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from app.module.admin.ModuleAdminAuth import ModuleAdminAuth
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException
from app.utils import errors as err
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceAdminAuth:
    """
    Interface for admin authentication
    """

    def __init__(self, process: ProcessSetting):
        """
        Initialize the admin authentication interface.

        :param process: Process settings
        :type process: ProcessSetting
        """
        self.process_settings = process
        try:
            self.module_admin_auth = ModuleAdminAuth(process)
        except RequestException:
            # Admin auth not configured - store None and handle gracefully in methods
            self.module_admin_auth = None

    def admin_login(self, username: str, password: str) -> tuple[dict, int]:
        """
        Authenticate admin with username and password.

        :param username: Admin username
        :type username: str
        :param password: Admin password
        :type password: str
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            if self.module_admin_auth is None:
                return create_api_base_response(None, err.ERROR_ADMIN_AUTH_NOT_CONFIG)

            if not self.module_admin_auth.check_admin_login(username, password):
                return create_api_base_response(None, err.ERROR_ADMIN_LOGIN_FAILED)

            # Generate the voucher for the authenticated admin
            ret = self.module_admin_auth.generate_voucher_from_admin(username)
            return create_api_base_response(ret)
        except RequestException as e:
            return create_api_base_response(None, e.error)

    def admin_logout(self, voucher_data: str) -> tuple[dict, int]:
        """
        Revoke the admin session associated with the given voucher.

        :param voucher_data: The raw JWT token from the Authorization header
        :type voucher_data: str
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            if self.module_admin_auth is None:
                return create_api_base_response(None, err.ERROR_ADMIN_AUTH_NOT_CONFIG)

            self.module_admin_auth.logout_admin(voucher_data)
        except RequestException as e:
            return create_api_base_response(None, e.error)
        return create_api_base_response(None)
