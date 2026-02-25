from __future__ import annotations
from typing import TYPE_CHECKING, Any

from app.auth.User import User
from app.module.mail.ModuleMail import ModuleMail
from app.module.auth.ModuleUserSource import ModuleUserSource
from app.config.settings.DomainSettings import MailSettings, MailSettingsObj
from app.utils.exceptions import RequestException
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils import constants as cs
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    

class InterfaceApiMailFolder:
    """
    Interface for folder-related mail operations.

    Handles mail folder operations for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.process_setting = process_setting
        self.user_domain_settings = user_domain_settings
        self.mail_settings = MailSettingsObj(user_domain_settings[MailSettings.subparent])
        self.user = user

        self.mail_module = ModuleMail(self.user, self.mail_settings)

    def get_folder_list(self, account_id: str) -> tuple[dict[str, Any], int]:
        """Retrieve the list of mail folders for a given account and return an ApiBaseResponse.

        Interface contract:
        - Catches module exceptions (RequestException, ValidationError)
        - Converts module data to API format
        - Returns tuple (response_dict, http_status_code)
        
        :param account_id: The account identifier
        :type account_id: str
        :return: tuple of (API response dict, HTTP status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            folder_list = self.mail_module.get_folder_list(account_id)
            return create_api_base_response(folder_list), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_list: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def create_folder(self, account_id: str, folder_name: str, parent_path:str = "") -> tuple[dict[str, Any], int]:
        """Create a new mail folder for the configured account and return an ApiBaseResponse.

        Interface contract:
        - Catches module exceptions (RequestException, ValidationError)
        - Converts module data to API format
        - Returns tuple (response_dict, http_status_code)

        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: Name of the folder to create
        :type folder_name: str
        :param parent_path: Path of the parent
        :type parent_path: str

        :return: tuple of (API response dict, HTTP status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            folder_data = self.mail_module.create_folder(account_id, folder_name, parent_path)
            return create_api_base_response(folder_data), 201
        except RequestException as ex:
            logger_api.error("Request exception in create_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_one_folder(self, account_id: str, folder_name: str) -> tuple[dict[str, Any], int]:
        """Retrieve details of a specific mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            folder_details = self.mail_module.get_one_folder(account_id, folder_name)
            return create_api_base_response(folder_details), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_one_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_folder(self, account_id: str, folder_name: str) -> tuple[str|dict[str, Any], int]:
        """Delete a mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder to delete
        :type folder_name: str
        :return: A tuple of (empty string or error dict, status code)
        :rtype: tuple[Union[str, dict[str, Any]], int]
        """
        try:
            self.mail_module.delete_folder(account_id, folder_name)
            return "", 204
        except RequestException as ex:
            logger_api.error("Request exception in delete_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_mails(
        self, account_id: str, folder_name: str, mail_uids: list[int]
    ) -> tuple[dict[str, Any], int]:
        """Delete multiple mails by ID by delegating the list to the module layer.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uids: List of mail UIDs to delete (ints)
        :type mail_uids: List[int]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            result = self.mail_module.delete_mails(folder_name, mail_uids)
            return create_api_base_response(result), 200
        except RequestException as ex:
            logger_api.error("Request exception in delete_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def update_folder(self, account_id: str, folder_name: str, folder_data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The current name of the folder
        :type folder_name: str
        :param folder_data: dictionary containing update data (name, subscribed, type)
        :type folder_data: dict[str, Any]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            updated_folder = self.mail_module.update_folder(folder_name, folder_data)
            return create_api_base_response(updated_folder), 200
        except RequestException as ex:
            logger_api.error("Request exception in update_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def move_mails(
        self, account_id: str, folder_name: str, mail_uids: list[int], to_folder_name: str
    ) -> tuple[dict[str, Any], int]:
        """Move multiple mails to another folder.
        Will be used by batch-action

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the source folder
        :type folder_name: str
        :param mail_uids: List of mail UIDs to move
        :type mail_uids: List[int]
        :param to_folder_name: The ID of the destination folder
        :type to_folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            result = self.mail_module.move_mails(folder_name, mail_uids, to_folder_name)
            return create_api_base_response(result), 200
        except RequestException as ex:
            logger_api.error("Request exception in move_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status


    def expunge_folder(self, account_id: str, folder_name: str, expunge_data:dict) -> tuple[dict[str, Any], int]:
        """Expunge all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder to expunge
        :type folder_name: str
        :return: A tuple of (API response dict with mail_deleted count, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        do_subfolders = expunge_data["do_subfolders"]
        try:
            result = self.mail_module.expunge_folder(account_id, folder_name, do_subfolders)
            return create_api_base_response(result), 200
        except RequestException as ex:
            logger_api.error("Request exception in expunge_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def purge_folder_mails(self, account_id: str, folder_name: str, purge_data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Purge all mails in the specified folder.
        
        Mark mails as deleted (optionally before a specific date).
        If permanently_delete is True, also expunge the folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param purge_data: dictionary containing purge options (do_subfolders, permanently_delete, date)
        :type purge_data: dict[str, Any]
        :return: A tuple of (empty string or error dict, status code)
        :rtype: tuple[Union[str, dict[str, Any]], int]
        """
        try:
            return create_api_base_response(self.mail_module.purge_folder_mails(account_id, folder_name, purge_data)), 200
        except RequestException as ex:
            logger_api.error("Request exception in purge_folder_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def export_folder_mails(self, account_id: str, folder_name: str) -> tuple[dict[str, Any], int]:
        """Export all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            export_data = self.mail_module.export_folder_mails(folder_name)
            return create_api_base_response(export_data), 200
        except RequestException as ex:
            logger_api.error("Request exception in export_folder_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_folder_share(self, account_id: str, folder_path: str) -> tuple[dict[str, Any], int]:
        """Get share information for the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The ID of the folder
        :type folder_path: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            share_info: dict[str, dict[str, Any]] = {}

            # Only Instantiate Module User Source if we need it
            module_us: ModuleUserSource|None = None

            for identifier, rights in  self.mail_module.get_folder_share(account_id, folder_path):
                if identifier == self.user.login_mail_server:
                    continue
                if identifier == "anyone":
                    #Special indentifier means it is acl for everyone than can auth on the mail server
                    share_info[identifier] = {
                        "user_class": cs.USER_CLASS_ANY,
                        "c_email": "",
                        "cn": "",
                        "uid": "",
                        "rights": rights
                    }
                    continue

                if module_us is None:
                    module_us = ModuleUserSource.init_from_domain_settings(self.user_domain_settings)
                #See if the identifier is known by us
                user = User(identifier)
                module_us.fill_user(user)
                if user.anonymous:
                    #The user was not found
                    share_info[identifier] = {
                        "user_class": cs.USER_CLASS_ANON,
                        "c_email": "",
                        "cn": "",
                        "uid": identifier,
                        "rights": rights
                    }
                else:
                    #TODO handlre groups. They start with '@'
                    share_info[identifier] = {
                        "user_class": cs.USER_CLASS_USER,
                        "c_email": user.mail,
                        "cn": user.cn,
                        "uid": user.uid,
                        "rights": rights
                    }
            return create_api_base_response(share_info), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_share: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def share_folder(self, account_id: str, folder_path: str, share_data: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Share the specified folder with another user.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The ID of the folder
        :type folder_path: str
        :param share_data: List of users with their rights configuration
        :type share_data: List[dict[str, Any]]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            share_info: dict[str, dict[str, Any]] = {}

            # Only Instantiate Module User Source if we need it
            module_us: ModuleUserSource|None = None

            for identifier, rights in self.mail_module.share_folder(account_id, folder_path, share_data):
                #TODO find a clerver way to factor this loop with get_folder_share()
                if identifier == self.user.login_mail_server:
                    continue
                if identifier == "anyone":
                    #Special indentifier means it is acl for everyone than can auth on the mail server
                    share_info[identifier] = {
                        "user_class": cs.USER_CLASS_ANY,
                        "c_email": "",
                        "cn": "",
                        "uid": "",
                        "rights": rights
                    }
                    continue

                if module_us is None:
                    module_us = ModuleUserSource.init_from_domain_settings(self.user_domain_settings)
                #See if the identifier is known by us
                user = User(identifier)
                module_us.fill_user(user)
                if user.anonymous:
                    #The user was not found
                    share_info[identifier] = {
                        "user_class": cs.USER_CLASS_ANON,
                        "c_email": "",
                        "cn": "",
                        "uid": identifier,
                        "rights": rights
                    }
                else:
                    #TODO handlre groups. They start with '@'
                    share_info[identifier] = {
                        "user_class": cs.USER_CLASS_USER,
                        "c_email": user.mail,
                        "cn": user.cn,
                        "uid": user.uid,
                        "rights": rights
                    }

            return create_api_base_response(share_info), 200
        except RequestException as ex:
            logger_api.error("Request exception in share_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
