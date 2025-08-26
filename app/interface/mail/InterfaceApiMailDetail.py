from typing import TYPE_CHECKING, Any
import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses
import email.utils
import time

from app.utils.exceptions import RequestException
from app.module.mail.ModuleMail import ModuleMail

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

class InterfaceApiMailDetail:
    """
    Interface for the ApiMailDetail API.
    """
    def __init__(self) -> None:
        self.module = ModuleMail(server="dovecot", port=143)

    def get_mail_detail(self, account_id: int, folder_id: str, mail_id: int) -> dict:
        """
        Retrieve detailed information about a specific mail.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :param mail_id: The unique identifier of the mail.
        :type mail_id: int
        :return: Detailed mail information.
        :rtype: dict
        """
        username = "sogo-tests1@example.org"
        password = "sogo"
        return self.module.get_mail_detail(username, password, folder_id, str(mail_id))
