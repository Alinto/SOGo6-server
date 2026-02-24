from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, List, Union, Tuple
from marshmallow import ValidationError

from app.utils.exceptions import RequestException
from app.module.mail.ModuleMail import ModuleMail
from app.config.settings.DomainSettings import MailSettings, MailSettingsObj, UserSourceSettings, UserSourceSettingsObj
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils import errors as err
from app.utils.logger.logger import logger_api
from app.utils import constants as cs
from app.utils.strings import get_imap_config_from_url

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User

UserConfType = Union[Dict[str, Any], List[Dict[str, Any]]]

class InterfaceApiMailMail:
    """
    Interface for the ApiMailDetail API.
    Handles mail retrieval for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.process_setting = process_setting
        self.user_domain_settings = user_domain_settings
        self.mail_settings = MailSettingsObj(user_domain_settings[MailSettings.subparent])
        self.use_source_settings = UserSourceSettingsObj(user_domain_settings[UserSourceSettings.subparent][user.source_id])
        self.user = user

    def _get_user_conf(self, account_id: str) -> dict:
        user_mail_conf: dict = {}
        if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
            #Get info of the main account
            user_mail_conf["username"] = self.user.login_mail_server
            user_mail_conf["password"] = self.user.password
            user_mail_conf["type"] = self.mail_settings.SOGO_D_MAIL_SERVER_TYPE
            my_server = self.mail_settings.get_mail_server_settings_for_type(self.mail_settings.SOGO_D_MAIL_SERVER_TYPE)
            #DEPRECATED but legacy
            if self.mail_settings.SOGO_D_MAIL_SERVER_TYPE == "imap" and self.user.imap_host:
                #extract host from user source
                new_config = get_imap_config_from_url(self.user.imap_host)
                my_server.update(new_config)
            user_mail_conf.update(my_server)
        else:
            if not self.user.profile.external_accounts or account_id not in self.user.profile.external_accounts:
                raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, error=err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)
            user_mail_conf = self.user.profile.external_accounts[account_id]
        return user_mail_conf


    def get_mail_list(
        self, account_id: str, folder_name: str, first: int, last: int
    ) -> Tuple[int, Dict[str, Any], int]:
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
        :rtype: Tuple[int, Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            result, total_count = module.get_folder_mails(folder_name, first, last)
            return total_count, create_api_base_response(result), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_mail_list: %s", ex.messages)
            return 0, create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_mail_list: %s", str(ex))
            return 0, create_api_base_response(None, ex.error_code), ex.http_status


    def get_mail_detail(self, account_id: str, folder_name: str, mail_uid: int) -> Tuple[Dict[str, Any], int]:
        """Retrieve detailed information about a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            mail_detail = module.get_mail_detail(folder_name, mail_uid)
            return create_api_base_response(mail_detail), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_mail_detail: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_mail_detail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_mail(self, account_id: str, folder_name: str, mail_uid: int) -> Tuple[Dict[str, Any], int]:
        """Delete a specific mail (mark as deleted).

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: A tuple of (API response dict with deleted mail UID, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            result = module.delete_mail(folder_name, mail_uid)
            return create_api_base_response(result), 204
        except ValidationError as ex:
            logger_api.error("Validation error in delete_mail: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in delete_mail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def reply_mail(self, account_id: str, folder_name: str, mail_uid: int) -> Tuple[Dict[str, Any], int]:
        """Reply to a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            reply_data = module.reply_mail(folder_name, mail_uid)
            return create_api_base_response(reply_data), 200
        except ValidationError as ex:
            logger_api.error("Validation error in reply_mail: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in reply_mail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def forward_mail(self, account_id: str, folder_name: str, mail_uid: int) -> Tuple[Dict[str, Any], int]:
        """Forward a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            forward_data = module.forward_mail(folder_name, mail_uid)
            return create_api_base_response(forward_data), 200
        except ValidationError as ex:
            logger_api.error("Validation error in forward_mail: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in forward_mail: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_mail_raw(self, account_id: str, folder_name: str, mail_uid: int) -> Tuple[Dict[str, Any], int]:
        """Retrieve the raw content of a specific mail.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            raw_content = module.get_mail_raw(folder_name, mail_uid)
            return create_api_base_response(raw_content), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_mail_raw: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_mail_raw: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
