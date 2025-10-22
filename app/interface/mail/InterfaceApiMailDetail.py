from typing import TYPE_CHECKING, Optional, Dict, Any, List, Union
from app.utils.exceptions import RequestException
from app.module.mail.ModuleMail import ModuleMail

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

UserConfType = Union[Dict[str, Any], List[Dict[str, Any]]]

class InterfaceApiMailDetail:
    """
    Interface for the ApiMailDetail API.
    Handles mail retrieval for one or multiple configured IMAP accounts.
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

    def get_mail_detail(self, account_id: int, folder_name: str, mail_uid: int) -> dict:
        """Retrieve detailed information about a specific mail.

        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: A dictionary containing detailed mail information.
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.get_mail_detail(conf, folder_name, mail_uid)
