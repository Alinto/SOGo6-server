from typing import TYPE_CHECKING, Optional, Dict, Any, List, Union

from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


UserConfType = Union[Dict[str, Any], List[Dict[str, Any]]]

class InterfaceApiMailAccount:
    """
    Interface for the ApiMailAccount API.
    Handles mailbox operations for one or more configured accounts.
    """

    def __init__(self, process_setting: Optional["ProcessSetting"] = None, user_conf: UserConfType = None, server: Optional[str] = None, port: Optional[int] = None) -> None:
        self.process_setting = process_setting
        self.user_conf = user_conf
        self.module = ModuleMail(server=server or "dovecot", port=port or 143)

    def _get_user_conf(self, account_id: int) -> dict:
        """
        Selects and validates the user configuration for a given account ID.
        """
        if not self.user_conf:
            raise RequestException("No mailbox configuration available")

        # Normalize to a list for simpler handling
        conf_list = self.user_conf if isinstance(self.user_conf, list) else [self.user_conf]
        if not (0 <= account_id < len(conf_list)):
            raise RequestException(f"Invalid account_id {account_id} (0..{len(conf_list)-1})")

        conf = conf_list[account_id]

        required_fields = ["username", "password", "type"] #TODO: future classe User?
        missing = [f for f in required_fields if not conf.get(f)]
        if missing:
            raise RequestException(f"Missing fields in account config: {', '.join(missing)}")

        return conf

    def get_folder_list(self, account_id: int) -> dict:
        """Retrieve the list of mail folders for a given account.

        :param account_id: The account identifier.
        :type account_id: int
        :return: A dictionary containing the status, data (list of folder names), and any errors.
        :rtype: dict
        """
        user_conf = self._get_user_conf(account_id)
        return self.module.get_folder_list(user_conf)

    def create_folder(self, account_id: int, folder_name: str) -> dict:
        """Create a new mail folder for the configured account.
        
        :param account_id: The account identifier.
        :type account_id: int
        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :return: A dictionary containing the status, data (created folder info), and any errors.
        :rtype: dict
        """
        user_conf = self._get_user_conf(account_id)
        return self.module.create_folder(user_conf, folder_name)
