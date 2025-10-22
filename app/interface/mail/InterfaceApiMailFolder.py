from typing import TYPE_CHECKING, Optional, Dict, Any, List, Union
from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException

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

    def get_mail_list(self, account_id: int, folder_name: str, page: int = 1, per_page: int = 20) -> dict:
        """Retrieve a list of mails in a specific folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param page: The page number for pagination
        :type page: int
        :param per_page: Number of mails per page
        :type per_page: int
        :return: A dictionary containing the list of mails, pagination info, and total count.
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.get_folder_mails(conf, folder_name, page=page, per_page=per_page)

    def delete_folder(self, account_id: int, folder_name: str) -> dict:
        """Delete a mail folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder to delete
        :type folder_name: str
        :return: A dictionary indicating success or failure of the operation.
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.delete_folder(conf, folder_name)

    def delete_mails(self, account_id: int, folder_name: str, mail_uids: List[int]) -> dict:
        """Delete multiple mails by ID by delegating the list to the module layer.

        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uids: List of mail UIDs to delete (ints)
        :type mail_uids: List[int]
        :return: Result dictionary returned by the module (status, data, errors)
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.delete_mails(conf, folder_name, mail_uids)

    def delete_all_mail_in_folder(self, account_id: int, folder_name: str, before_date: str | None) -> dict:
        """Delete all mails in a folder, optionally before a specific date.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param before_date: Optional date string to delete mails before this date
        :type before_date: str | None
        :return: A dictionary indicating the result of the delete operation.
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.delete_all_mail_in_folder(conf, folder_name, before_date)

    def move_mails(self, account_id: int, folder_name: str, mail_uids: List[int], to_folder_name: str) -> dict:
        """Move multiple mails to another folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the source folder
        :type folder_name: str
        :param mail_uids: List of mail UIDs to move
        :type mail_uids: List[int]
        :param to_folder_name: The ID of the destination folder
        :type to_folder_name: str
        :return: A dictionary indicating which mails were moved and which failed.
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.move_mails(conf, folder_name, mail_uids, to_folder_name)

    def expunge_folder(self, account_id: int, folder_name: str) -> dict:
        """Expunge all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder to expunge
        :type folder_name: str
        :return: A dictionary indicating the result of the expunge operation.
        :rtype: dict
        """
        conf = self._get_user_conf(account_id)
        return self.module.expunge_mailbox(conf, folder_name)
