import imaplib
from typing import List, Optional, Any
import re
import email
import datetime
import socket
#from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_imap
from app.manager.mail.AbstractMailClient import AbstractMailClient


class ClientImap(AbstractMailClient):
    """
    IMAP client implementation for Dovecot using imaplib.
    """

    def __init__(self, server: str, port: int = 143) -> None:
        """
        Initialize the IMAP client.

        :param server: IMAP server address.
        :type server: str
        :param port: IMAP port (default: 143).
        :type port: int
        :returns: None
        """
        self.server = server
        self.port = port
        self.connection: Optional[imaplib.IMAP4] = None


    # @retry(
    #    stop=stop_after_attempt(3),               # max 3 tentatives
    #    wait=wait_exponential(multiplier=1, min=2, max=10),  # Attendre de plus en plus longtemps entre chaque tentative
    #    retry=retry_if_exception_type((socket.error, imaplib.IMAP4.error)),
    #    reraise=True
    #)
    def connect(self) -> None:
        """
        Connect to the IMAP server.

        :raises ConnectionError: If the server cannot be reached.
        :raises TimeoutError: If the connection attempt times out.
        :raises Exception: For other unexpected IMAP errors.
        """
        logger_imap.debug("Connecting to IMAP server %s:%d", self.server, self.port)
        try:
            self.connection = imaplib.IMAP4(self.server, self.port)
            logger_imap.info("Successfully connected to IMAP server %s:%d", self.server, self.port)

        except socket.gaierror as e:
            # Erreur de résolution DNS ou IP invalide
            logger_imap.error("Invalid server address %s:%d - %s", self.server, self.port, e)
            raise ConnectionError(f"Unable to resolve server {self.server}") from e

        except (socket.timeout, TimeoutError) as e:
            # Timeout réseau
            logger_imap.error("Connection to IMAP server %s:%d timed out", self.server, self.port)
            raise TimeoutError(f"Connection to {self.server}:{self.port} timed out") from e

        except ConnectionRefusedError as e:
            # Port fermé ou refus de connexion
            logger_imap.error("Connection refused by IMAP server %s:%d", self.server, self.port)
            raise ConnectionError(f"Connection refused by {self.server}:{self.port}") from e

        except imaplib.IMAP4.error as e:
            # Erreur spécifique IMAP
            logger_imap.error("IMAP error while connecting to %s:%d - %s", self.server, self.port, e)
            raise Exception(f"IMAP error: {e}") from e
        except Exception as e:
            # Pour toute autre erreur inattendue
            logger_imap.exception("Unexpected error while connecting to IMAP server %s:%d", self.server, self.port)
            raise

    def login(self, username: str, password: str) -> None:
        """
        Login to the IMAP server.

        :param username: The username to login with.
        :type username: str
        :param password: The password to login with.
        :type password: str
        :raises Exception: If login failed.
        :returns: None
        """
        logger_imap.info("Logging in as %s", username)
        if self.connection is None:
            self.connect()
        assert self.connection is not None
        typ, data = self.connection.login(username, password)
        if typ != 'OK':
            raise RequestException("Failed to login to IMAP server.")

    def create_folder(self, folder_name: str) -> None:
        """
        Create the specified mail folder.

        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :raises Exception: If creation fails.
        """
        logger_imap.debug("Calling ClientImap: Creating folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")
        typ, _ = self.connection.create(folder_name)
        if typ != 'OK':
            raise RequestException(f"Failed to create folder '{folder_name}'.")

    def delete_folder(self, folder_name: str) -> None:
        """
        Delete the specified mail folder.

        :param folder_name: The name of the folder to delete.
        :type folder_name: str
        :raises Exception: If deletion fails.
        """
        logger_imap.debug("Calling ClientImap: Deleting folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")
        typ, _ = self.connection.delete(folder_name)
        if typ != 'OK':
            raise RequestException(f"Failed to delete folder '{folder_name}'.")

    def list_mailboxes(self) -> List[bytes]:
        """
        List all mailboxes/folders for the user.

        :raises Exception: If listing mailboxes failed or not connected.
        :returns: List of mailboxes in bytes format.
        :rtype: list[bytes]
        """
        if self.connection is None:
            raise RequestException("Not connected.")
        typ, mailbox_list = self.connection.list()
        if typ != 'OK':
            raise RequestException("Failed to list mailboxes.")
        if mailbox_list is None:
            return []
        return [m for m in mailbox_list if isinstance(m, bytes)]

    def expunge_mailbox(self, mailbox: str) -> None:
        """
        Expunge (permanently remove emails marked as deleted) from the specified mailbox.

        :param mailbox: The mailbox/folder name.
        :type mailbox: str
        :raises Exception: If expunging fails.
        :returns: None
        :rtype: None
        """
        logger_imap.debug("Calling ClientImap: Expunging mailbox '%s'", mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        typ, _ = self.connection.select(mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")
        typ, _ = self.connection.expunge()
        if typ != 'OK':
            raise RequestException(f"Failed to expunge mailbox {mailbox}.")

    def mark_all_mails_in_folder_deleted_and_copy_to_trash(self, mailbox: str, before_date: str | None) -> int:
        """
        Mark as deleted all mails in folder before the given date (YYYY-MM-DD).
        Also copies them to the "Trash" folder.
        Returns number of mails marked as deleted.

        :param mailbox: The mailbox/folder name.
        :type mailbox: str
        :param before_date: Date string in YYYY-MM-DD format to mark mails before this date
        :type before_date: str | None
        :raises Exception: If marking fails.
        :returns: Number of mails marked as deleted.
        :rtype: int
        """
        logger_imap.debug("Calling ClientImap: Marking all mails in folder '%s' as deleted before date '%s'", mailbox, before_date)
        if self.connection is None:
            raise RequestException("Not connected.")

        typ, _ = self.connection.select(mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")

        typ, data = self.connection.search(None, "ALL")
        if typ != 'OK':
            raise RequestException(f"Failed to search mails in {mailbox}.")

        mail_ids = data[0].split()
        marked_count = 0

        if before_date is not None:
            target_date = datetime.datetime.strptime(before_date, "%Y-%m-%d")

        for num in mail_ids:
            if before_date is not None:
                typ, msg_data = self.connection.fetch(num, '(BODY.PEEK[HEADER.FIELDS (DATE)])')
                if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                raw_headers = msg_data[0][1]
                msg = email.message_from_bytes(raw_headers)
                mail_date_str = msg.get('Date', '')
                try:
                    mail_date = email.utils.parsedate_to_datetime(mail_date_str)
                except Exception:
                    continue  # Ignore si la date est mal formatée

                if mail_date >= target_date:
                    continue
            #copy to trash
            typ, _ = self.connection.copy(num, "Trash")
            if typ != 'OK':
                continue
            # Mark mail as \Deleted
            typ, _ = self.connection.store(num, '+FLAGS', '\\Deleted')
            if typ == 'OK':
                marked_count += 1
        return marked_count

    def fetch_all_full_mails(self, mailbox: str) -> List[Any]:
        """
        Fetch all mails with RFC822 and FLAGS from a given mailbox.
        :param mailbox: The mailbox/folder name.
        :type mailbox: str
        :raises Exception: If fetching mails fails.
        :returns: List of mails with their raw bytes and flags.
        :rtype: List[Any]
        """
        logger_imap.debug("Calling ClientImap: Fetching all full mails from mailbox '%s'", mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        typ, _ = self.connection.select(mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")
        typ, data = self.connection.search(None, "ALL")
        if typ != 'OK':
            raise RequestException(f"Failed to search mails in {mailbox}.")
        mail_ids = data[0].split()
        mail_list = []
        for num in mail_ids:
            # Fetch RFC822 and FLAGS
            typ, msg_data = self.connection.fetch(num, '(RFC822 FLAGS)')
            if typ == 'OK' and msg_data and isinstance(msg_data[0], tuple):
                mail_bytes = msg_data[0][1]
                # Parse FLAGS from response (msg_data[0][0] is header)
                flags_match = re.search(rb'FLAGS \((.*?)\)', msg_data[0][0])
                flags: list[str] = []
                if flags_match:
                    flags = flags_match.group(1).decode().split()
                mail_list.append({'mail_bytes': mail_bytes, 'flags': flags})
        return mail_list

    def fetch_mail(self, mailbox: str, mail_id: str) -> bytes:
        """
        Fetch the full RFC822 message for a specific mail by its IMAP id.

        :param mailbox: The mailbox/folder name.
        :param mail_id: The IMAP mail id (sequence number).
        :return: The raw RFC822 bytes of the mail.
        """
        logger_imap.debug("Calling ClientImap: Fetching mail '%s' from mailbox '%s'", mail_id, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not mail_id or not mail_id.isdigit() or int(mail_id) <= 0:
            raise RequestException(f"Invalid mail id: {mail_id}")
        typ, _ = self.connection.select(mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")
        typ, msg_data = self.connection.fetch(str(mail_id), '(RFC822)')
        if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
            raise RequestException(f"Mail {mail_id} not found in {mailbox}.")
        # On retourne les bytes du mail
        return msg_data[0][1]

    def copy_mail_to_mailbox(self, mailbox: str, mail_id: str, dest_mailbox: str) -> None:
        """
        Copy a mail from one mailbox to another (e.g., to Trash).

        :param mailbox: The source mailbox/folder name.
        :param mail_id: The IMAP mail id (sequence number).
        :param dest_mailbox: The destination mailbox/folder name.
        :return: None
        """
        logger_imap.debug("Calling ClientImap: Copying mail '%s' from mailbox '%s' to mailbox '%s'", mail_id, mailbox, dest_mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not mail_id or not mail_id.isdigit() or int(mail_id) <= 0:
            raise RequestException(f"Invalid mail id: {mail_id}")
        typ, _ = self.connection.select(mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")
        typ, _ = self.connection.copy(str(mail_id), dest_mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to copy mail {mail_id} to {dest_mailbox}.")

    def add_flags_to_mail(self, mailbox: str, mail_id: str, flags: list[str]) -> None:
        """
        Add one or more flags to a mail in a mailbox.

        :param mailbox: The mailbox/folder name.
        :param mail_id: The IMAP mail id (sequence number).
        :param flags: List of IMAP flags to add (e.g., ['\\Seen', '\\Deleted']).
        """
        logger_imap.debug("Calling ClientImap: Adding flags %s to mail '%s' in mailbox '%s'", flags, mail_id, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        typ, _ = self.connection.select(mailbox)
        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")
        # IMAP expects flags as a string separated by spaces
        flags_str = ' '.join(flags)
        typ, _ = self.connection.store(str(mail_id), '+FLAGS', flags_str)
        if typ != 'OK':
            raise RequestException(f"Failed to add flags {flags} to mail {mail_id} in {mailbox}.")

    def logout(self) -> None:
        """
        Logout from the IMAP server and close the connection.

        :returns: None
        """
        logger_imap.info("Logging out from IMAP server")
        if self.connection:
            self.connection.logout()
            self.connection = None

#testing
if __name__ == "__main__":
    #client = ClientImap(server="192.168.21.81")
    client = ClientImap(server="dovecot")
    print("Connecting to IMAP server...")
    client.login("sogo-tests1@example.org", "sogo")
    mailboxes = client.list_mailboxes()
    print("Mailboxes found:", mailboxes)

    if mailboxes:
        first_mb = mailboxes[0].decode()
        mailbox_name = first_mb.split()[-1]
        print(f"Using mailbox: {mailbox_name}")

        mails = client.fetch_all_full_mails(mailbox_name)
        print(f"Number of mails in {mailbox_name}: {len(mails)}")
        for i, mail in enumerate(mails, 1):
            print(f"\n--- Mail #{i} ---\n{mail}")
    else:
        print("No mailboxes found.")



    client.logout()
