from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, List, Union, Tuple
from marshmallow import ValidationError

from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils import errors as err
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

UserConfType = Union[Dict[str, Any], List[Dict[str, Any]]]

class InterfaceApiMailFolder:
    """
    Interface for folder-related mail operations.

    Handles mail folder operations for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: ProcessSetting = None, user_conf: UserConfType | None = None) -> None:
        self.process_setting = process_setting
        self.user_conf = user_conf

    def _get_user_conf(self, account_id: int) -> Dict[str, Any]:
        """
        Select and validate the configuration for the given account ID.
        """
        if not self.user_conf:
            raise RequestException("No mailbox configuration available")

        conf_list = self.user_conf if isinstance(self.user_conf, list) else [self.user_conf]

        if not (0 <= account_id < len(conf_list)):
            raise RequestException(f"Invalid account_id {account_id} (0..{len(conf_list)-1})")

        conf = conf_list[account_id]

        required_fields = ["username", "password", "type"]
        missing = [f for f in required_fields if not conf.get(f)]
        if missing:
            raise RequestException(f"Missing fields in account config: {', '.join(missing)}")

        if conf["type"].lower() != "imap":
            raise RequestException(f"Unsupported mail type '{conf['type']}' (expected 'imap')")

        return conf

    def get_folder_list(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Retrieve the list of mail folders for a given account and return an ApiBaseResponse.

        Interface contract:
        - Catches module exceptions (RequestException, ValidationError)
        - Converts module data to API format
        - Returns tuple (response_dict, http_status_code)
        
        :param account_id: The account identifier
        :type account_id: int
        :return: Tuple of (API response dict, HTTP status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            user_conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=user_conf)
            folder_list = module.get_folder_list()
            # Module returns List[Dict] with full folder details
            return create_api_base_response(folder_list), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_folder_list: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_list: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def create_folder(self, account_id: int, folder_name: str) -> Tuple[Dict[str, Any], int]:
        """Create a new mail folder for the configured account and return an ApiBaseResponse.

        Interface contract:
        - Catches module exceptions (RequestException, ValidationError)
        - Converts module data to API format
        - Returns tuple (response_dict, http_status_code)

        :param account_id: The account identifier
        :type account_id: int
        :param folder_name: Name of the folder to create
        :type folder_name: str
        :return: Tuple of (API response dict, HTTP status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            user_conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=user_conf)
            folder_data = module.create_folder(folder_name)
            return create_api_base_response(folder_data), 201
        except ValidationError as ex:
            logger_api.error("Validation error in create_folder: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in create_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status


    def delete_folder(self, account_id: int, folder_name: str) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Delete a mail folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder to delete
        :type folder_name: str
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            module.delete_folder(folder_name)
            return "", 204
        except ValidationError as ex:
            logger_api.error("Validation error in delete_folder: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in delete_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_mails(
        self, account_id: int, folder_name: str, mail_uids: List[int]
    ) -> Tuple[Dict[str, Any], int]:
        """Delete multiple mails by ID by delegating the list to the module layer.

        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uids: List of mail UIDs to delete (ints)
        :type mail_uids: List[int]
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            result = module.delete_mails(folder_name, mail_uids)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            logger_api.error("Validation error in delete_mails: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in delete_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_all_mail_in_folder(
        self, account_id: int, folder_name: str, before_date: str | None
    ) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Delete all mails in a folder, optionally before a specific date.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param before_date: Optional date string to delete mails before this date
        :type before_date: str | None
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            module.delete_all_mail_in_folder(folder_name, before_date)
            return "", 204
        except ValidationError as ex:
            logger_api.error("Validation error in delete_all_mail_in_folder: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in delete_all_mail_in_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def move_mails(
        self, account_id: int, folder_name: str, mail_uids: List[int], to_folder_name: str
    ) -> Tuple[Dict[str, Any], int]:
        """Move multiple mails to another folder.
        Will be used by batch-action

        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the source folder
        :type folder_name: str
        :param mail_uids: List of mail UIDs to move
        :type mail_uids: List[int]
        :param to_folder_name: The ID of the destination folder
        :type to_folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            result = module.move_mails(folder_name, mail_uids, to_folder_name)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            logger_api.error("Validation error in move_mails: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in move_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def expunge_folder(self, account_id: int, folder_name: str) -> Tuple[Dict[str, Any], int]:
        """Expunge all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder to expunge
        :type folder_name: str
        :return: A tuple of (API response dict with mail_deleted count, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            result = module.expunge_folder(folder_name)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            logger_api.error("Validation error in expunge_folder: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in expunge_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def update_folder(self, account_id: int, folder_name: str, folder_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The current name of the folder
        :type folder_name: str
        :param folder_data: Dictionary containing update data (name, subscribed, type)
        :type folder_data: Dict[str, Any]
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            updated_folder = module.update_folder(folder_name, folder_data)
            return create_api_base_response(updated_folder), 200
        except ValidationError as ex:
            logger_api.error("Validation error in update_folder: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in update_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_folder_details(self, account_id: int, folder_name: str) -> Tuple[Dict[str, Any], int]:
        """Retrieve details of a specific mail folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            folder_details = module.get_folder_details(folder_name)
            return create_api_base_response(folder_details), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_folder_details: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_details: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def purge_folder_mails(self, account_id: int, folder_name: str, purge_data: Dict[str, Any]) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Purge all mails in the specified folder.
        
        Mark mails as deleted (optionally before a specific date).
        If permanentlyDelete is True, also expunge the folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param purge_data: Dictionary containing purge options (applyToSubfolders, permanentlyDelete, date)
        :type purge_data: Dict[str, Any]
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            return create_api_base_response(module.purge_folder_mails(folder_name, purge_data)), 200
        except ValidationError as ex:
            logger_api.error("Validation error in purge_folder_mails: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in purge_folder_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def export_folder_mails(self, account_id: int, folder_name: str) -> Tuple[Dict[str, Any], int]:
        """Export all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            export_data = module.export_folder_mails(folder_name)
            return create_api_base_response(export_data), 200
        except ValidationError as ex:
            logger_api.error("Validation error in export_folder_mails: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in export_folder_mails: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_folder_share(self, account_id: int, folder_name: str) -> Tuple[Dict[str, Any], int]:
        """Get share information for the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            share_info = module.get_folder_share(folder_name)
            return create_api_base_response(share_info), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_folder_share: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_share: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def share_folder(self, account_id: int, folder_name: str, share_data: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], int]:
        """Share the specified folder with another user.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param share_data: List of users with their rights configuration
        :type share_data: List[Dict[str, Any]]
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            result = module.share_folder(folder_name, share_data)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            logger_api.error("Validation error in share_folder: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in share_folder: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
