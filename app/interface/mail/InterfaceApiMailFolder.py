from typing import TYPE_CHECKING, Optional, Dict, Any, List, Union, Tuple
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

    def __init__(self, process_setting: "ProcessSetting" = None, user_conf: Optional[UserConfType] = None) -> None:
        self.process_setting = process_setting
        self.user_conf = user_conf
        self.module = ModuleMail()

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
            folder_list = self.module.get_folder_list(user_conf)
            # Module returns List[Dict], wrap it in the "folders" key
            return create_api_base_response({"folders": folder_list}), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            folder_data = self.module.create_folder(user_conf, folder_name)
            return create_api_base_response(folder_data), 201
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404


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
            self.module.delete_folder(conf, folder_name)
            return "", 204
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            result = self.module.delete_mails(conf, folder_name, mail_uids)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            self.module.delete_all_mail_in_folder(conf, folder_name, before_date)
            return "", 204
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

    def move_mails(
        self, account_id: int, folder_name: str, mail_uids: List[int], to_folder_name: str
    ) -> Tuple[Dict[str, Any], int]:
        """Move multiple mails to another folder.
        
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
            result = self.module.move_mails(conf, folder_name, mail_uids, to_folder_name)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            result = self.module.expunge_folder(conf, folder_name)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            updated_folder = self.module.update_folder(conf, folder_name, folder_data)
            return create_api_base_response(updated_folder), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            folder_details = self.module.get_folder_details(conf, folder_name)
            return create_api_base_response(folder_details), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            return create_api_base_response(self.module.purge_folder_mails(conf, folder_name, purge_data)), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            export_data = self.module.export_folder_mails(conf, folder_name)
            return create_api_base_response(export_data), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            share_info = self.module.get_folder_share(conf, folder_name)
            return create_api_base_response(share_info), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

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
            result = self.module.share_folder(conf, folder_name, share_data)
            return create_api_base_response(result), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404
