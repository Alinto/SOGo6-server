import imaplib
from typing import List, Any, Dict
import re
import datetime
import socket
import base64

from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger_imap
from app.manager.mail.ClientMailServer import ClientMailServer

imaplib.Debug = 4  # Maximum debug output from imaplib


class ClientImap(ClientMailServer):
    """
    IMAP client implementation for Dovecot using imaplib.
    """

    def __init__(self, server: str, port: int = 143) -> None:
        """
        Initialize the IMAP client.
        """
        self.server = server
        self.port = port
        self.connection: imaplib.IMAP4 | None = None

    def connect(self) -> None:
        """
        Connect to the IMAP server.
        """
        logger_imap.debug("Connecting to IMAP server %s:%d", self.server, self.port)
        try:
            self.connection = imaplib.IMAP4(self.server, self.port)
            logger_imap.info("Successfully connected to IMAP server %s:%d", self.server, self.port)

        except (socket.gaierror, socket.timeout, TimeoutError, ConnectionRefusedError, imaplib.IMAP4.error) as e:
            logger_imap.error("IMAP connection error to %s:%d - %s", self.server, self.port, e)
            raise RequestException(f"IMAP connection error: {e}") from e

        except Exception as e:
            logger_imap.exception("Unexpected error while connecting to IMAP server %s:%d", self.server, self.port)
            raise BugException(f"Unexpected error during IMAP connection: {e}") from e

    def login(self, username: str, password: str, auth_mech: str | None = None) -> None:
        """Login to the IMAP server.

        :param username: The username for authentication.
        :type username: str
        :param password: The password for authentication (or OAuth2 access token when auth_mech is XOAUTH2).
        :type password: str
        :param auth_mech: Optional authentication mechanism ("None", "PLAIN", "XOAUTH2"). Case-insensitive.
        :type auth_mech: str | None
        :raises RequestException: If login fails.
        """
        logger_imap.info("Logging in as %s using auth_mech=%s", username, auth_mech)
        if self.connection is None:
            self.connect()

        conn = self.connection
        if conn is None:
            raise BugException("IMAP connection unexpectedly None after connect().")

        mech = (auth_mech or "None")
        mech_lower = mech.lower() if isinstance(mech, str) else "none"

        try:
            if mech_lower in ("none", "null", ""):
                # Classic LOGIN
                typ = conn.login(username, password)
                if typ[0] != 'OK':
                    raise RequestException("Failed to login to IMAP server.")
                return

            if mech_lower == "plain":   #TODO: revoir ça
                # SASL PLAIN: authzid\0authcid\0password ; authzid usually empty
                def plain_auth(challenge: bytes) -> str:
                    resp = b"\x00" + username.encode("utf-8") + b"\x00" + password.encode("utf-8")
                    return base64.b64encode(resp).decode("ascii")
                typ = conn.authenticate('PLAIN', plain_auth)
                # imaplib.authenticate returns a tuple similar to other commands
                if isinstance(typ, tuple) and typ[0] != 'OK':
                    raise RequestException("PLAIN authentication failed.")
                return

            if mech_lower == "xoauth2": #TODO: revoir ça
                # XOAUTH2: base64("user={user}\x01auth=Bearer {access_token}\x01\x01")
                def xoauth2_auth(challenge: bytes) -> str:
                    auth_string = f"user={username}\x01auth=Bearer {password}\x01\x01"
                    return base64.b64encode(auth_string.encode("utf-8")).decode("ascii")
                typ = conn.authenticate('XOAUTH2', xoauth2_auth)
                if isinstance(typ, tuple) and typ[0] != 'OK':
                    raise RequestException("XOAUTH2 authentication failed.")
                return

            # Unknown mechanism
            raise RequestException(f"Unsupported authentication mechanism: {auth_mech}")

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"IMAP login/authentication error: {e}") from e

    def create_folder(self, folder_name: str) -> None:
        """
        Create a new folder (mailbox) on the IMAP server.

        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :raises RequestException: If folder creation fails.
        """
        logger_imap.debug("Creating folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")
        try:
            typ, _ = self.connection.create(folder_name)
            if typ != 'OK':
                raise RequestException(f"Failed to create folder '{folder_name}'.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while creating folder '{folder_name}': {e}") from e

    def delete_folder(self, folder_name: str) -> None:
        """
        Delete a folder (mailbox) from the IMAP server.
        :param folder_name: The name of the folder to delete.
        :type folder_name: str
        :raises RequestException: If folder deletion fails.
        """
        logger_imap.debug("Deleting folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")
        try:
            typ, _ = self.connection.delete(folder_name)
            if typ != 'OK':
                raise RequestException(f"Failed to delete folder '{folder_name}'.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while deleting folder '{folder_name}': {e}") from e

    def list_mailboxes(self) -> List[bytes]:
        """List all mailboxes (folders) on the IMAP server.

        :raises RequestException: If not connected to the server.
        :raises RequestException: If listing mailboxes fails.
        :return: A list of mailbox names.
        :rtype: List[bytes]
        """
        logger_imap.debug("Listing mailboxes")
        if self.connection is None:
            raise RequestException("Not connected.")
        try:
            typ, mailbox_list = self.connection.list()
            if typ != 'OK':
                raise RequestException("Failed to list mailboxes.")
            return [m for m in mailbox_list or [] if isinstance(m, bytes)]
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while listing mailboxes: {e}") from e

    def expunge_mailbox(self, mailbox: str) -> None:
        """Expunge all deleted messages in the specified mailbox.

        :param mailbox: The name of the mailbox to expunge.
        :type mailbox: str
        :raises RequestException: If not connected to the server.
        :raises RequestException: If expunging fails.
        """
        logger_imap.debug("Expunging mailbox '%s'", mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        try:
            typ, _ = self.connection.select(mailbox)
            if typ != 'OK':
                raise RequestException(f"Failed to select mailbox {mailbox}.")
            typ, _ = self.connection.expunge()
            if typ != 'OK':
                raise RequestException(f"Failed to expunge mailbox {mailbox}.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while expunging mailbox '{mailbox}': {e}") from e


    def get_mail_uids_before_date(
        self,
        mailbox: str,
        before_date: str | None = None,
        exclude_deleted: bool = True
    ) -> list[int]:
        """Get all mail UIDs from a mailbox, optionally filtered before a date.

        :param mailbox: The name of the mailbox to search.
        :type mailbox: str
        :param before_date: The cutoff date (YYYY-MM-DD). Only mails before this date are returned.
        :type before_date: str | None
        :param exclude_deleted: Whether to exclude deleted emails from the search.
        :type exclude_deleted: bool
        :return: A list of mail UIDs as integers.
        :rtype: list[int]
        :raises RequestException: If the search fails.
        """
        logger_imap.debug("Fetching mail UIDs from '%s' before '%s'", mailbox, before_date)

        if self.connection is None:
            raise RequestException("Not connected.")

        #select mailbox
        try:
            typ, _ = self.connection.select(mailbox)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"IMAP select error for mailbox '{mailbox}': {e}") from e

        if typ != 'OK':
            raise RequestException(f"Failed to select mailbox {mailbox}.")

        #build search criteria (date parsing isolated)
        criteria_parts: list[str] = []
        if exclude_deleted:
            criteria_parts.append("NOT DELETED")

        if before_date:
            try:
                dt = datetime.datetime.strptime(before_date, "%Y-%m-%d")
                formatted_date = dt.strftime("%d-%b-%Y")
                criteria_parts.append(f"BEFORE {formatted_date}")
            except ValueError as exc:
                raise RequestException(f"Invalid date format: {before_date}. Expected YYYY-MM-DD.") from exc

        criteria = "(" + " ".join(criteria_parts) + ")" if criteria_parts else "ALL"

        #perform search
        try:
            typ, data = self.connection.uid('SEARCH', criteria)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"IMAP SEARCH error in mailbox '{mailbox}' with criteria '{criteria}': {e}") from e

        if typ != 'OK':
            raise RequestException(f"Failed to search mails in {mailbox} with criteria {criteria}.")

        #parse results (per-UID parsing isolated to get detailed per-UID warnings)
        if not data or not data[0]:
            return []

        mail_uids_bytes = data[0].split()
        uids: list[int] = []
        for uid_b in mail_uids_bytes:
            if not uid_b:
                continue
            try:
                # decode using ASCII (UIDs are numeric ASCII)
                uid_str = uid_b.decode("ascii")
            except UnicodeDecodeError as e:
                logger_imap.warning("Skipping UID with undecodable bytes %r in mailbox %s: %s", uid_b, mailbox, e)
                continue

            try:
                uid_int = int(uid_str)
                if uid_int > 0:
                    uids.append(uid_int)
            except ValueError as e:
                logger_imap.warning("Skipping non-numeric UID '%s' in mailbox %s: %s", uid_str, mailbox, e)
                continue

        return uids

    def fetch_all_full_mails(self, mailbox: str) -> List[Dict[str, Any]]: # Note: Consider using pagination for large mailboxes.
        """Fetch all full mails with UIDs from a mailbox.

        :param mailbox: The mailbox to fetch mails from.
        :type mailbox: str
        :raises RequestException: If the operation fails.
        :return: A list of dictionaries containing mail UID (int), raw bytes, and flags.
        :rtype: List[Dict[str, Any]]
        """
        logger_imap.debug("Fetching all full mails from '%s'", mailbox)

        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, _ = self.connection.select(mailbox)
        except Exception as e:
            logger_imap.error("Error selecting mailbox '%s': %s", mailbox, e)
            raise RequestException(f"Error selecting mailbox '{mailbox}': {e}") from e

        if typ != 'OK':
            logger_imap.error("SELECT command failed with type: %s", typ)
            raise RequestException(f"Failed to select mailbox '{mailbox}'.")

        try:
            typ, msg_data = self.connection.uid('FETCH', '1:*', '(RFC822 FLAGS)')
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error fetching mails from '{mailbox}': {e}") from e

        if typ != 'OK':
            raise RequestException(f"Failed to fetch mails from '{mailbox}'.")

        mail_list: List[Dict[str, Any]] = []
        if not msg_data:
            return mail_list

        for part in msg_data:
            if not isinstance(part, tuple):
                continue
            if len(part) < 2:
                continue
            # Using explicit unpacking
            meta = part[0] # pylint: disable=unsubscriptable-object
            mail_bytes = part[1] # pylint: disable=unsubscriptable-object

            if not isinstance(meta, bytes) or not isinstance(mail_bytes, bytes):
                continue
            try:
                # Extract UID
                uid_match = re.search(rb'UID (\d+)', meta)
                if not uid_match:
                    # Skip entries where UID can't be parsed
                    continue
                uid = int(uid_match.group(1).decode())
                # Extract FLAGS
                flags_match = re.search(rb'FLAGS \((.*?)\)', meta)
                flags = flags_match.group(1).decode().split() if flags_match else []
            except (AttributeError, IndexError, UnicodeDecodeError, ValueError) as e:
                logger_imap.warning("Error parsing UID/flags for a mail: %s", e)
                continue

            mail_list.append({
                "uid": uid,
                "mail_bytes": mail_bytes,
                "flags": flags
            })

        return mail_list

    def fetch_mail(self, mailbox: str, mail_uid: int) -> bytes:
        """Fetch a mail from a specific mailbox using UID.

        :param mailbox: The mailbox containing the mail
        :type mailbox: str
        :param mail_uid: The UID of the mail to fetch (int)
        :type mail_uid: int
        :raises RequestException: If the operation fails
        :return: The raw bytes of the fetched mail
        :rtype: bytes
        """
        logger_imap.debug("Fetching mail UID '%s' from '%s'", mail_uid, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            typ, _ = self.connection.select(mailbox)
            if typ != 'OK':
                logger_imap.error("SELECT command failed with type: %s", typ)
                raise RequestException(f"Failed to select mailbox {mailbox}.")
            typ, msg_data = self.connection.uid('FETCH', str(mail_uid), '(RFC822)')
            if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
                logger_imap.error("FETCH command failed with type: %s", typ)
                raise RequestException(f"Mail UID {mail_uid} not found in {mailbox}.")
            return msg_data[0][1]
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while fetching mail UID {mail_uid}: {e}") from e

    def copy_mail_to_mailbox(self, mailbox: str, mail_uid: int, dest_mailbox: str) -> None:
        """Copy a mail from one mailbox to another using UID.

        :param mailbox: The source mailbox
        :type mailbox: str
        :param mail_uid: The UID of the mail to copy (int)
        :type mail_uid: int
        :param dest_mailbox: The destination mailbox
        :type dest_mailbox: str
        :raises RequestException: If the operation fails
        """
        logger_imap.debug("Copying mail UID '%s' from '%s' to '%s'", mail_uid, mailbox, dest_mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            typ, _ = self.connection.select(mailbox)
            if typ != 'OK':
                logger_imap.error("SELECT command failed with type: %s", typ)
                raise RequestException(f"Failed to select mailbox {mailbox}.")
            typ, _ = self.connection.uid('COPY', str(mail_uid), dest_mailbox)
            if typ != 'OK':
                logger_imap.error("COPY command failed with type: %s", typ)
                raise RequestException(f"Failed to copy mail UID {mail_uid} to {dest_mailbox}.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while copying mail UID {mail_uid}: {e}") from e

    def add_flags_to_mail(self, mailbox: str, mail_uid: int, flags: list[str]) -> None:
        """Add flags to a mail using UID.

        :param mailbox: The mailbox containing the mail
        :type mailbox: str
        :param mail_uid: The UID of the mail to modify (int)
        :type mail_uid: int
        :param flags: The flags to add to the mail
        :type flags: list[str]
        :raises RequestException: If the operation fails
        """
        logger_imap.debug("Adding flags %s to mail UID '%s' in '%s'", flags, mail_uid, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            typ, _ = self.connection.select(mailbox)
            if typ != 'OK':
                raise RequestException(f"Failed to select mailbox {mailbox}.")

            flags_str = '(' + ' '.join(flags) + ')'
            typ, _ = self.connection.uid('STORE', str(mail_uid), '+FLAGS', flags_str)
            if typ != 'OK':
                logger_imap.error("STORE command failed with type: %s", typ)
                raise RequestException(f"Failed to add flags {flags} to mail UID {mail_uid} in {mailbox}.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while adding flags to mail UID {mail_uid}: {e}") from e

    def logout(self) -> None:
        """Log out from the IMAP server.

        :raises RequestException: If the operation fails.
        """
        logger_imap.info("Logging out from IMAP server")
        if self.connection:
            try:
                self.connection.logout()
            except (imaplib.IMAP4.error, OSError, socket.error) as e:
                raise RequestException(f"Error while logging out: {e}") from e
            finally:
                self.connection = None
