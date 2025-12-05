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

class InterfaceApiMailIdentity:
    """
    Interface for identity-related mail operations.

    Handles mail identity operations for one or multiple configured IMAP accounts.
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

    def get_mailbox_identities(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Get identities for this mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            identities = self.module.get_mailbox_identities(conf)
            return create_api_base_response(identities), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_mailbox_identities: %s", ex.messages)
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox_identities: %s", str(ex))
            return create_api_base_response(str(ex), ex.error_code), 400

    def create_mailbox_identity(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Create a new identity for this mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            identity_data = self.module.create_mailbox_identity(conf)
            return create_api_base_response(identity_data), 201
        except ValidationError as ex:
            logger_api.error("Validation error in create_mailbox_identity: %s", ex.messages)
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox_identity: %s", str(ex))
            return create_api_base_response(str(ex), ex.error_code), 400

    def get_identity(self, account_id: int, identity_id: int) -> Tuple[Dict[str, Any], int]:
        """Retrieve a specific mail identity.
        
        :param account_id: The account identifier
        :type account_id: int
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            identity = self.module.get_identity(conf, identity_id)
            return create_api_base_response(identity), 200
        except ValidationError as ex:
            logger_api.error("Validation error in get_identity: %s", ex.messages)
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in get_identity: %s", str(ex))
            return create_api_base_response(str(ex), ex.error_code), 400

    def delete_identity(self, account_id: int, identity_id: int) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Delete a specific mail identity.
        
        :param account_id: The account identifier
        :type account_id: int
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            self.module.delete_identity(conf, identity_id)
            return "", 204
        except ValidationError as ex:
            logger_api.error("Validation error in delete_identity: %s", ex.messages)
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in delete_identity: %s", str(ex))
            return create_api_base_response(str(ex), ex.error_code), 400

    def update_identity(self, account_id: int, identity_id: int) -> Tuple[Dict[str, Any], int]:
        """Update a specific mail identity.
        
        :param account_id: The account identifier
        :type account_id: int
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            conf = self._get_user_conf(account_id)
            identity_data = self.module.update_identity(conf, identity_id)
            return create_api_base_response(identity_data), 200
        except ValidationError as ex:
            logger_api.error("Validation error in update_identity: %s", ex.messages)
            return create_api_base_response(ex.messages, err.ERROR_VALIDATION_ERROR), 400
        except RequestException as ex:
            logger_api.error("Request exception in update_identity: %s", str(ex))
            return create_api_base_response(str(ex), ex.error_code), 400
