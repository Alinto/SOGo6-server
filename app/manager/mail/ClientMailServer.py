from abc import ABCMeta, abstractmethod
from typing import List, Any

class ClientMailServer(metaclass=ABCMeta):
    """
    Abstract class for mail clients.
    All mail clients should inherit from this class and implement its methods.
    """

    @abstractmethod
    def connect(self) -> None:
        """Connect to the mail server."""

    @abstractmethod
    def login(self, username: str, password: str) -> None:
        """Login to the mail server."""

    @abstractmethod
    def list_mailboxes(self) -> List[bytes]:
        """List all mailboxes/folders for the user."""

    @abstractmethod
    def fetch_mail(self, mailbox: str, mail_uid: int) -> Any | None:
        """Fetch a full mail by UID from a mailbox."""

    @abstractmethod
    def logout(self) -> None:
        """Logout from the mail server."""

    @abstractmethod
    def delete_folder(self, folder_name: str) -> None:
        """Delete the specified mail folder."""

    @abstractmethod
    def create_folder(self, folder_name: str) -> None:
        """Create the specified mail folder."""

    @abstractmethod
    def fetch_all_full_mails(self, mailbox: str) -> List[Any]:
        """Fetch all full mails (RFC822) from a given mailbox/folders."""
