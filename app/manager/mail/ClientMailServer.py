from abc import ABCMeta, abstractmethod
from typing import Any, Iterator

class ClientMailServer(metaclass=ABCMeta):
    """
    Abstract class for mail clients.
    All mail clients should inherit from this class and implement its methods.
    """
    def __init__(self) -> None:
        """
        Just set a param to tell if the client needs to authenticate or not
        """
        self.connected = False
        self.authenticated = False

    @abstractmethod
    def connect(self) -> None:
        """Connect to the mail server."""

    @abstractmethod
    def login(self, username: str, password: str) -> None:
        """Login to the mail server."""

    @abstractmethod
    def list_folders(self) -> list[dict[str, Any]]:
        """List all folders for the user, each item is:

        {
            "name": str, name of the folder,
            "path": str, path of the folder (meaning parent1/parent2/name),
            "filter_path": str, same as path but fot the filerting server,
            "type": str, type of the folder, see MAIL_SERVER_FOLDER_TYPE in utils.contants
            "flags": set, flag of this folder
            "children": list, this same dict for children folders
            "subscribed": int 1/0, subscribed means the user want to see this folder and its mails
            "unseen_count": int, number of mails not already seen
            "message_count": int, total number of mails in this folders
        }
        """

    @abstractmethod
    def get_one_folder(self, folder_path: str) -> dict[str, Any]:
        """Get one folder, dict is:

        {
            "name": str, name of the folder,
            "path": str, path of the folder (meaning parent1/parent2/name),
            "filter_path": str, same as path but fot the filerting server,
            "type": str, type of the folder, see MAIL_SERVER_FOLDER_TYPE in utils.contants
            "flags": set, flag of this folder
            "children": list, this same dict for children folders
            "subscribed": int 1/0, subscribed means the user want to see this folder and its mails
            "unseen_count": int, number of mails not already seen
            "message_count": int, total number of mails in this folders
        }
        """

    @abstractmethod
    def create_folder(self, folder_name: str, parent_path: str = "", auto_sub:bool = True) -> str:
        """
        Create the specified mail folder, automatically sub by default.
        Return the path of the folder
        """

    @abstractmethod
    def delete_folder(self, folder_path: str, do_children:bool = True) -> None:
        """
        Delete the specified mail folder. Meaning:
        - permanently remove it if already in trash folder
        - move it to trash folder if not

        do_children = True means all the children/subfolders will be affected too.
        """

    @abstractmethod
    def purge_folder(self, folder_path: str, before_date: str = "", do_children: bool = True, permanently: bool = False) -> int:
        """
        Delete all mails inside the folder older than before_date
        If permanently is True, to not place them in Trash folder

        :param folder_path: _description_
        :type folder_path: str
        :param before_date: _description_, defaults to None
        :type before_date: str | None, optional
        :return: _description_
        :rtype: int
        """

    @abstractmethod
    def expunge_folder(self, folder_path: str, do_children: bool = True) -> int:
        """
        Expunge, meaning removing all mails tags "\\Deleted", in the specified folder.

        :param folder_path: path of the folder
        :type folder_path: str
        :return: Nymber of messages expunged
        :rtype: int
        """

    @abstractmethod
    def get_acl(self, folder_path: str) -> Iterator[tuple[str, dict[str, int]]]:
        """Get the Access Control list (ACL) for a specific folder.

        Uses the IMAP GETACL command to retrieve folder permissions and converts
        them to SOGo rights format.

        :param folder_path: The name of the folder to get ACL for.
        :type folder_path: str
        :return: list of tuples (identifier, rights_dict) where identifier is a username 
                 and rights_dict is a dictionary of SOGo rights
        :rtype: list[tuple[str, dict[str, int]]]
        :raises RequestException: If not connected to the server or if getting ACL fails.
        """

    @abstractmethod
    def set_acl(self, folder_path: str, identifier: str, rights: dict[str, Any]) -> None:
        """Set ACL rights for a specific user/identifier on a folder.

        Uses the IMAP SETACL command to grant permissions. Converts SOGo rights
        dictionary to IMAP ACL string format.

        :param folder_path: The name of the folder.
        :type folder_path: str
        :param identifier: The user identifier (email, username, or special like 'anyone').
        :type identifier: str
        :param rights: dictionary of SOGo rights (e.g., {"userCanViewFolder": 1, "userCanReadMails": 1})
        :type rights: dict[str, Any]
        :raises RequestException: If not connected to the server or if setting ACL fails.
        """

    @abstractmethod
    def delete_acl(self, folder_path: str, identifier: str) -> None:
        """Delete ACL rights for a specific user/identifier on a folder.

        Uses the IMAP DELETEACL command to remove all permissions for an identifier.

        :param folder_path: The name of the folder.
        :type folder_path: str
        :param identifier: The user identifier to remove ACL for.
        :type identifier: str
        :raises RequestException: If not connected to the server or if deleting ACL fails.
        """

    @abstractmethod
    def fetch_all_mails_with_content(self, folder_path: str, number_of_mails: int, offset: int) -> Iterator[dict]:
        """
        https://datatracker.ietf.org/doc/html/rfc9051#name-fetch-response
        Fetch a specific number of mails from a mailbox with full details.

        First yield the total number of mails into the folder:
        {"nb_mails": 500}
        If not 0, yield a dict for each mail, from most recent to oldest
        {
            "uid": uid, str
            "mail": mail object, Message
            "flags": flags_dict, dict
            "size": size, int
        }

        :param mailbox: The mailbox to fetch mails from.
        :type mailbox: str
        :param number_of_mails: The number of mails to fetch.
        :type number_of_mails: int
        :param offset: The offset of the mail to fetch.
        :type number_of_mails: int
        :raises RequestException: If fetching mails fails
        :return: A tuple of (list of mail dicts with full details, total count)
        :rtype: tuple[list[dict[str, Any]], int]
        """

    @abstractmethod
    def fetch_all_mails_without_content(self, folder_path: str, number_of_mails: int, offset: int) -> Iterator[dict]:
        """
        https://datatracker.ietf.org/doc/html/rfc9051#name-fetch-response
        Fetch a specific number of mails from a mailbox with full details.

        {
            "uid": uid, str
            "mail": mail object, Message
            "flags": flags_dict, dict
            "size": size, int
            "has_attachment": bool
        }

        Always yield the total number of mails of the folder
        Then yield mail by mail, from the most recent to the oldest

        :param mailbox: The mailbox to fetch mails from.
        :type mailbox: str
        :param number_of_mails: The number of mails to fetch.
        :type number_of_mails: int
        :param offset: The offset of the mail to fetch.
        :type number_of_mails: int
        :raises RequestException: If fetching mails fails
        :return: A tuple of (list of mail dicts with full details, total count)
        :rtype: tuple[list[dict[str, Any]], int]
        """

    @abstractmethod
    def fetch_mail(self, folder_path: str, mail_uid: str) -> dict[str, Any]:
        """Fetch a mail by UID from a mailbox.
         ```    
        {
            "uid": uid, str
            "mail_bytes": mail object, Message
            "flags": flags_dict, dict
            "size": size, int
        }
        ```
        """

    @abstractmethod
    def fetch_mail_raw(self, folder_path: str, mail_uid: str) -> str:
        """Fetch a the raw mail (eml) by UID from a mailbox."""

    @abstractmethod
    def delete_mails_by_uid(self, folder_path: str, mail_uid: str|list[str], move_to_trash: bool = True, permanently: bool = True) -> None:
        """Delete a specific mail by UID according to the requested behaviour.

        :param folder_path: The folder containing the mail.
        :type folder_path: str
        :param mail_uid: The UID or a list of uids of the mail to delete.
        :type mail_uid: str or list[str]
        :param move_to_trash: Copy the mail to the Trash folder before deletion.
        :type move_to_trash: bool
        :param permanently: Expunge the mail after flagging it as deleted.
        :type permanently: bool
        :raises RequestException: If the operation fails.
        """

    @abstractmethod
    def add_flags_to_mail(self, folder_path: str, mail_uid: str, flags: list[str]) -> None:
        """Add flags to a mail using UID.
        Wrapper selecting folder then using uid_store_flags primitive.

        :param folder_path: The folder containing the mail.
        :type folder_path: str
        :param mail_uid: The UID of the mail to modify.
        :type mail_uid: int
        :param flags: list of flags to add (e.g., ['\\Seen', '\\Flagged']).
        :type flags: list[str]
        :raises RequestException: If the operation fails.
        """

    @abstractmethod
    def remove_flags_to_mail(self, folder_path: str, mail_uid: str, flags: list[str]) -> None:
        """remove flags to a mail using UID.
        Wrapper selecting folder then using uid_store_flags primitive.

        :param folder_path: The folder containing the mail.
        :type folder_path: str
        :param mail_uid: The UID of the mail to modify.
        :type mail_uid: int
        :param flags: list of flags to add (e.g., ['\\Seen', '\\Flagged']).
        :type flags: list[str]
        :raises RequestException: If the operation fails.
        """

    @abstractmethod
    def copy_mail_to_mailbox(self, folder_path: str, mail_uid: str, dest_folder_path: str, create_dest: bool = False) -> None:
        """Copy a mail from one mailbox to another using UID.
        Wrapper selecting folder_path then using uid_copy primitive.

        :param folder_path: The source folder_path.
        :type folder_path: str
        :param mail_uid: The UID of the mail to copy.
        :type mail_uid: int
        :param dest_folder_path: The destination folder_path.
        :type dest_folder_path: str
        :param create_dest: True if the folder needs to be created (or ensure that it's already exist)
        :param type: bool, default to False
        :raises RequestException: If the operation fails.
        """



    @abstractmethod
    def logout(self) -> None:
        """Logout from the mail server."""

    @abstractmethod
    def get_quota(self) -> dict[str, Any] | None:
        """Get quota information for the mailbox.

        Uses the IMAP GETQUOTAROOT command on the inbox folder.
        Returns None if the server does not support QUOTA or the command is unavailable.

        :return: Dictionary containing quota info, or None if unavailable:
            {
                "storage_used": int,   # storage used in KB
                "storage_limit": int,  # storage limit in KB (0 if unlimited)
            }
        :rtype: dict[str, Any] | None
        """
