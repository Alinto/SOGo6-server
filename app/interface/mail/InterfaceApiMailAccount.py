from typing import TYPE_CHECKING, List
from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

class InterfaceApiMailAccount:
    """
    Interface for the ApiMailAccount API.
    """

    def __init__(self, process_setting: "ProcessSetting" = None) -> None:
        self.module = ModuleMail(server="dovecot", port=143)

    def get_folder_list(self, account_id: int) -> dict:
        """
        Retrieve the list of mail folders for a given account.

        :param account_id: The account identifier.
        :type account_id: int
        :return: A dictionary containing the status, list of folder names, and any errors.
        :rtype: dict
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        return self.module.get_folder_list(username, password)

    def create_folder(self, account_id: int, folder_name: str) -> dict:
        """
        Create a new mail folder for a given account.
        
        :param account_id: The account identifier.
        :type account_id: int
        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :raises RequestException: If the folder cannot be created.
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        ret_status, ret_error = self.module.create_folder(username, password, folder_name)
        return {"status": ret_status, "errors": ret_error}
