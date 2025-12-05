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

class InterfaceApiMailMailbox:
    """
    Interface for mailbox-related mail operations.

    Handles mail mailbox operations for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: "ProcessSetting" = None, user_conf: Optional[UserConfType] = None) -> None:
        self.process_setting = process_setting
        self.user_conf = user_conf
        self.module = ModuleMail()

    def _get_user_conf(self, account_id: int) -> Dict[str, Any]:
        """
        Select and validate the configuration for a given account ID.
        """
        if not self.user_conf:
            raise RequestException("No mailbox configuration available")

        # Normalize to list for consistent handling
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

    def list_mailboxes(self) -> Tuple[Dict[str, Any], int]:
        """List all configured mailboxes.
        
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            mailboxes = self.module.list_mailboxes(self.user_conf)
            return create_api_base_response({"mailboxes": mailboxes}), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

    def create_mailbox(self) -> Tuple[Dict[str, Any], int]:
        """Create a new mailbox (add external account).
        
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            mailbox_data = self.module.create_mailbox(self.user_conf)
            return create_api_base_response(mailbox_data), 201
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

    def update_mailbox(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Update mailbox settings.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            mailbox_data = self.module.update_mailbox(conf)
            return create_api_base_response(mailbox_data), 200
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404

    def delete_mailbox(self, account_id: int) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Delete a mailbox (only external accounts).
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            self.module.delete_mailbox(conf)
            return "", 204
        except ValidationError as ex:
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            return create_api_base_response(str(ex), ex.error_code), 404
