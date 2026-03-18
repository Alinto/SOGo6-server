from __future__ import annotations
from typing import TYPE_CHECKING, Any, cast

from io import BytesIO

from marshmallow import ValidationError

from app.utils.exceptions import RequestException
from app.module.mail.ModuleMail import ModuleMail
from app.config.settings.DomainSettings import MailSettings, MailSettingsObj
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils import errors as err
from app.utils.logger.logger import logger_api
from app.utils import constants as cs

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User


class InterfaceApiMailMail:
    """
    Interface for the ApiMailDetail API.
    Handles mail retrieval for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.process_setting = process_setting
        self.user_domain_settings = user_domain_settings
        self.mail_settings = MailSettingsObj(user_domain_settings[MailSettings.subparent])
        self.user = user

        self.mail_module = ModuleMail(self.user, self.mail_settings)

    def get_mail_list(
        self, account_id: str, folder_name: str, first: int, last: int
    ) -> tuple[int, dict[str, Any], int]:
        """Retrieve a list of mails in a specific folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param first: The first item index (0-based)
        :type first: int
        :param last: The last item index (0-based, exclusive)
        :type last: int
        :return: A tuple of (total_count, API response dict, status code)
        :rtype: tuple[int, dict[str, Any], int]
        """
        try:
            result, total_count = self.mail_module.get_folder_mails(account_id, folder_name, first, last)
            return total_count, create_api_base_response(result), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_mail_list: %s", str(ex))
            return 0, create_api_base_response(None, ex.error_code), ex.http_status


    def get_mail_detail(self, account_id: str, folder_name: str, mail_uid: str) -> tuple[dict[str, Any], int]:
        """Retrieve detailed information about a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            mail_detail = self.mail_module.get_mail_detail(account_id, folder_name, mail_uid)
            return create_api_base_response(mail_detail), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_mail_detail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_mail(self, account_id: str, folder_name: str, mail_uid: str) -> tuple[str|dict, int]:
        """Delete a specific mail (mark as deleted).

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A tuple of (API response dict with deleted mail UID, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            self.mail_module.delete_mails(account_id, folder_name, mail_uid)
            return "", 204
        except RequestException as ex:
            logger_api.error("Request exception in delete_mail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def reply_mail(self, account_id: str, folder_name: str, mail_uid: str) -> tuple[dict[str, Any], int]:
        """Reply to a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            reply_data = self.mail_module.reply_mail(account_id, folder_name, mail_uid)
            return create_api_base_response(reply_data), 200
        except RequestException as ex:
            logger_api.error("Request exception in reply_mail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def forward_mail(self, account_id: str, folder_name: str, mail_uid: str) -> tuple[dict[str, Any], int]:
        """Forward a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            forward_data = self.mail_module.forward_mail(account_id, folder_name, mail_uid)
            return create_api_base_response(forward_data), 200
        except RequestException as ex:
            logger_api.error("Request exception in forward_mail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_mail_raw(self, account_id: str, folder_name: str, mail_uid: str) -> tuple[dict[str, Any], int]:
        """Retrieve the raw content of a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            raw_content = self.mail_module.get_mail_raw(account_id, folder_name, mail_uid)
            return create_api_base_response(raw_content), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_mail_raw: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def mail_action(self, account_id: str, folder_name: str, mail_uid: str, action_data: dict[str, Any]) -> tuple[BytesIO|dict[str, Any], int]:
        """Perform an action on a specific mail.

        For the 'download' action, returns a Flask send_file response with the raw .eml content.
        For all other actions, returns a standard API response tuple.

        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :param action_data: Dictionary containing 'action' and optional 'data' fields
        :type action_data: Dict[str, Any]
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            result = self.mail_module.perform_mail_action(account_id, folder_name, mail_uid, action_data)
            if action_data["action"] in ("download", "zip"):
                # Cast send_file response to expected return type
                return cast(BytesIO, result), 200
            return create_api_base_response(cast(dict[str, Any], result)), 200
        except ValidationError as ex:
            logger_api.error("Validation error in mail_action: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in mail_action: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
