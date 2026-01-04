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

class InterfaceApiMailMailbox:
    """
    Interface for mailbox-related mail operations.

    Handles mail mailbox operations for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: ProcessSetting, user_conf: UserConfType | None = None) -> None:
        self.process_setting = process_setting
        self.user_conf = user_conf

    def _get_user_conf(self, account_id: int) -> Dict[str, Any]:
        """
        Select and validate the configuration for a given account ID.
        """
        if not self.user_conf:
            raise RequestException("No mailbox configuration available")

        # Normalize to list for consistent handling
        conf_list = self.user_conf if isinstance(self.user_conf, list) else [self.user_conf]

        if not 0 <= account_id < len(conf_list):
            raise RequestException(f"Invalid account_id {account_id} (0..{len(conf_list)-1})")

        conf = conf_list[account_id]

        required_fields = ["username", "password", "type"]
        missing = [f for f in required_fields if not conf.get(f)]
        if missing:
            raise RequestException(f"Missing fields in account config: {', '.join(missing)}")

        if conf["type"].lower() != "imap":
            raise RequestException(f"Unsupported mail type '{conf['type']}' (expected 'imap')")

        return conf

    def list_mailboxes(self) -> Tuple[Dict[str, Any], int]:
        """List all configured mailboxes.
        
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            module = ModuleMail(user_conf=self.user_conf)
            mailboxes = module.list_mailboxes()
            return create_api_base_response({"mailboxes": mailboxes}), 200
        except ValidationError as ex:
            logger_api.error("Validation error in list_mailboxes: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in list_mailboxes: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def create_mailbox(self) -> Tuple[Dict[str, Any], int]:
        """Create a new mailbox (add external account).
        
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            module = ModuleMail(user_conf=self.user_conf) #TODO: pas d'account id à ce niveau, comment on fait ?
            mailbox_data = module.create_mailbox()
            return create_api_base_response(mailbox_data), 201
        except ValidationError as ex:
            logger_api.error("Validation error in create_mailbox: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def update_mailbox(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Update mailbox settings.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            mailbox_data = module.update_mailbox()
            return create_api_base_response(mailbox_data), 200
        except ValidationError as ex:
            logger_api.error("Validation error in update_mailbox: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in update_mailbox: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def delete_mailbox(self, account_id: int) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Delete a mailbox (only external accounts).
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            module.delete_mailbox()
            return "", 204
        except ValidationError as ex:
            logger_api.error("Validation error in delete_mailbox: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in delete_mailbox: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def compose_email(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Compose a new email from the specified mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            email_data = module.compose_email()
            return create_api_base_response(email_data), 200
        except ValidationError as ex:
            logger_api.error("Validation error in compose_email: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in compose_email: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_mailbox_delegates(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Get delegates for this mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            delegates = module.get_mailbox_delegates()
            return create_api_base_response({"delegates": delegates}), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_mailbox_delegates: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox_delegates: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def create_mailbox_delegate(self, account_id: int, data: dict) -> Tuple[Dict[str, Any], int]:
        """Create a new delegate for this mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :param data: Delegate data
        :type data: dict
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            delegate_data = module.create_mailbox_delegate(data)
            return create_api_base_response(delegate_data), 201
        except ValidationError as ex:
            logger_api.error("Validation error in create_mailbox_delegate: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox_delegate: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def purge_mailbox(self, account_id: int) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Purge (all folders) from the specified mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            module = ModuleMail(user_conf=conf)
            module.purge_mailbox()
            return "", 204
        except ValidationError as ex:
            logger_api.error("Validation error in purge_mailbox: %s", ex.messages)
            return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in purge_mailbox: %s", str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
