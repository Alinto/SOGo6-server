from typing import TYPE_CHECKING, Any
import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses
from app.utils.exceptions import RequestException
from app.module.mail.ModuleMail import ModuleMail

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

class InterfaceApiMailFolder:
    """
    Interface for the ApiMailFolder API.
    """
    def __init__(self) -> None:
        self.module = ModuleMail(server="dovecot", port=143)

    def get_mail_list(self, account_id: int, folder_id: str, page: int = 1, per_page: int = 20) -> dict:
        """
        Retrieve the list of mails in a given folder.
        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :param page: Page number for pagination (default: 1)
        :type page: int
        :param per_page: Number of mails per page (default: 20)
        :type per_page: int
        :return: Dict with status, list of mails with parsed headers and attachment info, and any errors
        :rtype: dict
        :raises RequestException: If the folder cannot be found or mails cannot be retrieved.
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        return self.module.get_folder_mails(username, password, folder_id, page=page, per_page=per_page)

    def expunge_folder(self, account_id: int, folder_name: str) -> dict:
        """
        Expunge (delete) all mails marked as deleted from the specified folder.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_name: The folder name.
        :type folder_name: str
        :return: Dict with success/error
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        ret_status, ret_error = self.module.expunge_mailbox(username, password, folder_name)
        return {"status": ret_status, "errors": ret_error}

    def delete_folder(self, account_id: int, folder_id: str) -> dict:
        """
        Delete a mail folder for a given account.
        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :raises RequestException: If the folder cannot be deleted.
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        ret_status, ret_error = self.module.delete_folder(username, password, folder_id)
        return {"status": ret_status, "errors": ret_error}

    def delete_all_mail_in_folder(self, account_id: int, folder_id: str, before_date: str | None) -> dict:
        """
        Mark as deleted all mails in folder before the given date.
        Returns number of mails marked as deleted.
        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :param before_date: Date string in format YYYY-MM-DD. If None, all mails
        before the current date are marked as deleted.
        :type before_date: str | None
        :return: Dict with success/error and count of marked mails.
        :rtype: dict
        :raises RequestException: If the folder cannot be found or mails cannot be deleted.
        :Query params:
            before: date string (YYYY-MM-DD)
            default: None (all mails will be deleted)
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        ret_status, ret_error = self.module.delete_all_mail_in_folder(username, password, folder_id, before_date)
        return {"status": ret_status, "errors": ret_error}

    def delete_mails(self, account_id: int, folder_id: str, mail_ids: list[int]) -> dict:
        """
        Delete multiple mails by their identifiers.
        Returns dict with deleted and failed ids.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :param mail_ids: List of mail IDs to delete.
        :type mail_ids: list[int]
        :return: Dict with deleted and failed ids.
        :rtype: dict
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        deleted = []
        failed = []
        for mail_id in mail_ids:
            ret_status, ret_error = self.module.delete_mail_by_id(username, password, folder_id, str(mail_id))
            if ret_status:
                deleted.append(mail_id)
            else:
                failed.append({"id": mail_id, "error": ret_error})
        return {
            "status": len(failed) == 0,
            "deleted_ids": deleted,
            "failed_ids": failed,
            "errors": [error["error"] for error in failed]
        }

    def move_mails(self, account_id: int, from_folder_id: str, mail_ids: list[int], to_folder_id: str) -> dict:
        """
        Move multiple mails to another folder.
        
        :param account_id: The account identifier.
        :type account_id: int
        :param from_folder_id: The source folder identifier.
        :type from_folder_id: str
        :param mail_ids: List of mail IDs to move.
        :type mail_ids: list[int]
        :param to_folder_id: The target folder identifier.
        :type to_folder_id: str
        :return: Dict with moved and failed ids.
        :rtype: dict
        :raises RequestException: If mails cannot be moved.
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        moved = []
        failed = []
        for mail_id in mail_ids:
            ret_status, ret_error = self.module.move_mail(username, password, from_folder_id, str(mail_id), to_folder_id)
            if ret_status:
                moved.append(mail_id)
            else:
                failed.append({"id": mail_id, "error": ret_error})
        return {
            "status": len(failed) == 0,
            "moved_ids": moved,
            "failed_ids": failed,
            "errors": [error["error"] for error in failed]
        }
