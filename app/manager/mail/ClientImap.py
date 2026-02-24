import imaplib
from typing import List, Any, Dict, Tuple, cast
import re
import datetime
import socket
import base64

from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger_imap
from app.manager.mail.ClientMailServer import ClientMailServer
from app.utils import errors as err
from app.utils.constants import (
    USERCANVIEWFOLDER,
    USERCANREADMAILS,
    USERCANMARKMAILSREAD,
    USERCANINSERTMAILS,
    USERCANPOSTMAILS,
    USERCANCREATESUBFOLDERS,
    USERCANREMOVEFOLDER,
    USERCANERASEMAILS,
    USERCANEXPUNGEFOLDER,
    USERCANWRITEMAILS,
    USERCANADMINISTRATOR,
)

imaplib.Debug = 4  # Maximum debug output from imaplib


# IMAP ACL rights conversion utilities
# Mapping constants to centralize conversions between SOGo rights and IMAP ACL chars.
RIGHTS_MAP: Dict[str, str] = {
    USERCANVIEWFOLDER: "lr",            # lookup + read
    USERCANREADMAILS: "s",              # keep seen/unseen information (s)
    USERCANMARKMAILSREAD: "w",          # write (w)
    USERCANINSERTMAILS: "i",            # insert (i)
    USERCANPOSTMAILS: "p",              # post (p)
    USERCANCREATESUBFOLDERS: "k",       # create subfolders (k) (c is obsolete/alias)
    USERCANREMOVEFOLDER: "x",           # delete mailbox (x)
    USERCANERASEMAILS: "t",             # delete messages (t)
    USERCANEXPUNGEFOLDER: "e",          # expunge (e)
    USERCANWRITEMAILS: "w",             # same as mark mails read/write flags
    USERCANADMINISTRATOR: "a",          # administer (a)
}

# IMAP char -> list of SOGo keys to set when char present.
IMAP_TO_SOGO: Dict[str, List[str]] = {
    "s": [USERCANREADMAILS],
    "w": [USERCANMARKMAILSREAD, USERCANWRITEMAILS],
    "i": [USERCANINSERTMAILS],
    "p": [USERCANPOSTMAILS],
    "k": [USERCANCREATESUBFOLDERS],
    "c": [USERCANCREATESUBFOLDERS],  # obsolete alias for create
    "x": [USERCANREMOVEFOLDER],
    "t": [USERCANERASEMAILS],
    "e": [USERCANEXPUNGEFOLDER],
    "d": [USERCANREMOVEFOLDER, USERCANERASEMAILS, USERCANEXPUNGEFOLDER],  # obsolete -> x+t+e
    "a": [USERCANADMINISTRATOR],
}


def _convert_rights_to_imap(rights_dict: Dict[str, Any]) -> str:
    """Convert SOGo rights dictionary to IMAP ACL rights string using RIGHTS_MAP.

    Preserves order defined in RIGHTS_MAP and removes duplicates.
    
    :param rights_dict: Dictionary of SOGo rights (keys like "userCanViewFolder", values are truthy/falsy)
    :type rights_dict: Dict[str, Any]
    :return: IMAP ACL rights string (e.g., "lrswipkxtea")
    :rtype: str
    """
    if not rights_dict or not isinstance(rights_dict, dict):
        return ""

    imap_chars: List[str] = []
    seen = set()

    for sogo_key, imap_seq in RIGHTS_MAP.items():
        if rights_dict.get(sogo_key):
            for ch in imap_seq:
                if ch not in seen:
                    seen.add(ch)
                    imap_chars.append(ch)

    return "".join(imap_chars)


def _convert_imap_to_rights(imap_rights: str) -> Dict[str, int]:
    """Convert IMAP ACL rights string to SOGo rights dictionary using IMAP_TO_SOGO.

    Behaviours preserved:
    - userCanViewFolder is set only when both 'l' and 'r' present.
    - 'd' expands to x,t,e as before.
    
    :param imap_rights: IMAP ACL rights string (e.g., "lrswipkxtea")
    :type imap_rights: str
    :return: Dictionary of SOGo rights with integer values (0 or 1)
    :rtype: Dict[str, int]
    """
    # Initialize all rights to 0
    sogo_rights: Dict[str, int] = {
        USERCANVIEWFOLDER: 0,
        USERCANREADMAILS: 0,
        USERCANMARKMAILSREAD: 0,
        USERCANINSERTMAILS: 0,
        USERCANPOSTMAILS: 0,
        USERCANCREATESUBFOLDERS: 0,
        USERCANREMOVEFOLDER: 0,
        USERCANERASEMAILS: 0,
        USERCANEXPUNGEFOLDER: 0,
        USERCANWRITEMAILS: 0,
        USERCANADMINISTRATOR: 0
    }

    if not imap_rights:
        return sogo_rights

    rights_lower = imap_rights.lower()

    # Track presence of 'l' and 'r' for userCanViewFolder
    has_l = 'l' in rights_lower
    has_r = 'r' in rights_lower

    # Set flags based on IMAP_TO_SOGO mapping
    for ch, sogo_keys in IMAP_TO_SOGO.items():
        if ch in rights_lower:
            for key in sogo_keys:
                sogo_rights[key] = 1

    # Now handle l+r -> userCanViewFolder (must have both)
    if has_l and has_r:
        sogo_rights[USERCANVIEWFOLDER] = 1

    return sogo_rights


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
            raise RequestException(f"IMAP connection error: {e}", err.ERROR_IMAP_CONNECTION_FAILED) from e

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
            if mech_lower in ("login", "none", "null", ""):
                # Classic LOGIN
                typ = conn.login(username, password)
                if typ[0] != 'OK':
                    raise RequestException("Failed to login to IMAP server - Invalid credentials", err.ERROR_IMAP_UNAUTHORIZED)
                return

            if mech_lower == "plain":   #TODO: revoir ça
                # SASL PLAIN: authzid\0authcid\0password ; authzid usually empty
                def plain_auth(challenge: bytes) -> str:
                    resp = b"\x00" + username.encode("utf-8") + b"\x00" + password.encode("utf-8")
                    return base64.b64encode(resp).decode("ascii")
                typ = conn.authenticate('PLAIN', plain_auth)
                # imaplib.authenticate returns a tuple similar to other commands
                if isinstance(typ, tuple) and typ[0] != 'OK':
                    raise RequestException("PLAIN authentication failed - Invalid credentials", err.ERROR_IMAP_UNAUTHORIZED)
                return

            if mech_lower == "xoauth2": #TODO: revoir ça
                # XOAUTH2: base64("user={user}\x01auth=Bearer {access_token}\x01\x01")
                def xoauth2_auth(challenge: bytes) -> str:
                    auth_string = f"user={username}\x01auth=Bearer {password}\x01\x01"
                    return base64.b64encode(auth_string.encode("utf-8")).decode("ascii")
                typ = conn.authenticate('XOAUTH2', xoauth2_auth)
                if isinstance(typ, tuple) and typ[0] != 'OK':
                    raise RequestException("XOAUTH2 authentication failed - Invalid credentials", err.ERROR_IMAP_UNAUTHORIZED)
                return

            # Unknown mechanism
            raise BugException(f"Unsupported authentication mechanism: {auth_mech}")

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            # Authentication errors from imaplib
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["authent", "login", "credential", "password", "no permission"]):
                raise RequestException(f"IMAP authentication failed: {e}", err.ERROR_IMAP_UNAUTHORIZED) from e
            raise RequestException(f"IMAP login/authentication error: {e}", err.ERROR_IMAP_CONNECTION_FAILED) from e

    def select_mailbox(self, mailbox: str) -> int:
        """Select a mailbox (atomic).
        :param mailbox: The mailbox to select.
        :type mailbox: str
        :raises RequestException: If selecting the mailbox fails.
        :return: The number of messages in the selected mailbox.
        """
        logger_imap.debug("Selecting mailbox '%s'", mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        try:
            typ, data = self.connection.select(mailbox)
            if typ != 'OK':
                raise RequestException(f"Failed to select folder '{mailbox}'.", err.ERROR_FOLDER_NAME_NOT_FOUND)
            return int(data[0].decode() if data[0] is not None else 0)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"IMAP select error for folder '{mailbox}': {e}") from e

    def uid_copy(self, mail_uid: int, dest_mailbox: str) -> None:
        """Do UID COPY without selecting the mailbox itself (atomic).
        :param mail_uid: The UID of the mail to copy.
        :param dest_mailbox: The destination mailbox to copy the mail to.
        :raises RequestException: If UID COPY fails.
        """
        logger_imap.debug("UID COPY '%s' to '%s'", mail_uid, dest_mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            typ, _ = self.connection.uid('COPY', str(mail_uid), dest_mailbox)
            if typ != 'OK':
                raise RequestException(f"UID COPY failed for UID {mail_uid} to {dest_mailbox}.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error during UID COPY for UID {mail_uid}: {e}", err.ERROR_MAIL_UID_NOT_FOUND) from e

    def uid_store_flags(self, mail_uid: int, flags: List[str], operation: str = '+FLAGS') -> None:
        """Do UID STORE (FLAGS) without selecting the mailbox (atomic).
        :param mail_uid: The UID of the mail to modify.
        :param flags: List of flags to set/unset.
        :param operation: The operation to perform ('+FLAGS', '-FLAGS', or 'FLAGS').
        """
        logger_imap.debug("UID STORE %s '%s' flags %s", operation, mail_uid, flags)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            flags_str = '(' + ' '.join(flags) + ')'
            typ, _ = self.connection.uid('STORE', str(mail_uid), operation, flags_str)
            if typ != 'OK':
                raise RequestException(f"UID STORE failed for UID {mail_uid} with flags {flags}.")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error during UID STORE for UID {mail_uid}: {e}", err.ERROR_MAIL_UID_NOT_FOUND) from e

    def fetch_all_mails(self, mailbox: str, number_of_mails: int) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch a specific number of mails from a mailbox with full details.

        :param mailbox: The mailbox to fetch mails from.
        :type mailbox: str
        :param number_of_mails: The number of mails to fetch.
        :type number_of_mails: int
        :raises RequestException: If fetching mails fails
        :return: A tuple of (list of mail dicts with full details, total count)
        :rtype: Tuple[List[Dict[str, Any]], int]
        """
        logger_imap.debug("Fetching %d mails from '%s'", number_of_mails, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            mailbox_len = self.select_mailbox(mailbox)
            start = max(1, mailbox_len - number_of_mails + 1)
            end = mailbox_len
            range_arg = f'{start}:{end}'
            # Fetch full message, flags, and UID (size is included in BODY.PEEK[] response)
            typ, msg_data = self.connection.fetch(range_arg, '(BODY.PEEK[] FLAGS UID)')

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error fetching mails from '{mailbox}': {e}") from e

        if typ != 'OK':
            raise RequestException(f"Failed to fetch mails from '{mailbox}'.")

        mail_list: List[Dict[str, Any]] = []
        if not msg_data:
            return mail_list, mailbox_len
        for part in msg_data:
            if not isinstance(part, tuple):
                continue
            if len(part) < 2:
                continue
            meta, mail_bytes, *_ = part

            if not isinstance(meta, bytes) or not isinstance(mail_bytes, bytes):
                continue
            try:
                # Parse UID
                uid_match = re.search(rb'UID (\d+)', meta)
                if not uid_match:
                    continue
                uid = int(uid_match.group(1).decode())
                
                # Parse FLAGS
                flags_match = re.search(rb'FLAGS \((.*?)\)', meta)
                flags_list = flags_match.group(1).decode().split() if flags_match else []
                
                # Parse size from BODY.PEEK[] {size} format in meta
                size_match = re.search(rb'BODY\[?\]?\s*\{(\d+)\}', meta)
                size = int(size_match.group(1).decode()) if size_match else len(mail_bytes)
                
                # Structure flags
                flags_dict = {
                    'seen': '\\Seen' in flags_list,
                    'flagged': '\\Flagged' in flags_list,
                    'answered': '\\Answered' in flags_list,
                    'forwarded': '$Forwarded' in flags_list or '\\Forwarded' in flags_list,
                    'all': flags_list
                }
                
            except (AttributeError, IndexError, UnicodeDecodeError, ValueError) as e:
                logger_imap.warning("Error parsing UID/flags/size for a mail: %s", e)
                continue

            mail_list.append({
                "uid": uid,
                "mail_bytes": mail_bytes,
                "flags": flags_dict,
                "size": size
            })
        return list(reversed(mail_list)), mailbox_len

    def fetch_mails_by_uids(self, mailbox: str, uid_list: List[int]) -> List[Dict[str, Any]]:
        """Fetch mails for a list of UIDs (atomique: select + single FETCH for list).
        :param mailbox: The mailbox to fetch mails from.
        :type mailbox: str
        :param uid_list: List of mail UIDs to fetch.
        :type uid_list: List[int]
        :raises RequestException: If fetching mails fails
        :return: A list of mail dicts
        :rtype: List[Dict[str, Any]]
        """
        logger_imap.debug("Fetching mails by UIDs %s from '%s'", uid_list, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")

        if not uid_list:
            return []

        try:
            uid_set = ",".join(str(int(u)) for u in uid_list)
            # Use BODY.PEEK[] instead of RFC822 to avoid marking as read, and ensure UID is included
            typ, msg_data = self.connection.uid('FETCH', uid_set, '(BODY.PEEK[] FLAGS UID)')
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error fetching mails from '{mailbox}' for UIDs {uid_list}: {e}") from e

        if typ != 'OK':
            raise RequestException(f"Failed to fetch mails from '{mailbox}' for UIDs {uid_list}.")

        mail_list: List[Dict[str, Any]] = []
        if not msg_data:
            return mail_list

        for part in msg_data:
            if not isinstance(part, tuple):
                continue
            if len(part) < 2:
                continue
            meta = part[0]
            mail_bytes = part[1]

            if not isinstance(meta, bytes) or not isinstance(mail_bytes, bytes):
                continue
            try:
                uid_match = re.search(rb'UID (\d+)', meta)
                if not uid_match:
                    continue
                uid = int(uid_match.group(1).decode())
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

    def is_folder_in_trash(self, folder_name: str) -> bool:
        """Check if a folder is within the Trash folder hierarchy.

        A folder is considered to be in Trash if:
        - It is exactly "Trash" (case-insensitive)
        - It starts with "Trash/" (case-insensitive)
        
        :param folder_name: The name of the folder to check.
        :type folder_name: str
        :return: True if the folder is within Trash, False otherwise.
        :rtype: bool
        """
        self.select_mailbox(folder_name)
        folder_lower = folder_name.lower()
        return folder_lower == 'trash' or folder_lower.startswith('trash/')

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

    def list_mailboxes_detailed(self) -> List[Dict[str, Any]]:
        """List all mailboxes with detailed information including children.

        This method retrieves all top-level folders and their complete hierarchy
        with detailed information for each folder including message counts, subscriptions, etc.

        :raises RequestException: If not connected to the server.
        :raises RequestException: If listing mailboxes fails.
        :return: A list of folder dictionaries with full details and nested children.
        :rtype: List[Dict[str, Any]]
        """
        logger_imap.debug("Listing mailboxes with details")
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            # List top-level folders only (using "%" pattern)
            typ, mailbox_list = self.connection.list('""', '%')
            if typ != 'OK':
                raise RequestException("Failed to list mailboxes.")

            detailed_folders = []

            for item in mailbox_list or []:
                if not item or item == b'':
                    continue

                item_str = ""
                if isinstance(item, bytes):
                    item_str = item.decode('utf-8')
                elif isinstance(item, tuple):
                    item_str = item[0].decode('utf-8') if isinstance(item[0], bytes) else str(item[0])
                else:
                    item_str = str(item)

                # Parse folder name from LIST response
                name_match = re.search(r'"[^"]*"\s+"([^"]+)"', item_str)
                if not name_match:
                    name_match = re.search(r'"[^"]*"\s+(\S+)', item_str)

                if name_match:
                    folder_path = name_match.group(1)
                    try:
                        # Get full details for this folder (including children recursively)
                        folder_details = self.get_folder_details(folder_path)
                        detailed_folders.append(folder_details)
                    except RequestException as e:
                        logger_imap.warning("Failed to get details for folder '%s': %s", folder_path, e)
                        continue

            return detailed_folders

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while listing mailboxes: {e}") from e

    def expunge_folder(self, mailbox: str) -> int:
        """Expunge all deleted messages in the specified mailbox.

        :param mailbox: The name of the mailbox to expunge.
        :type mailbox: str
        :return: The number of messages that were expunged (permanently deleted).
        :rtype: int
        :raises RequestException: If not connected to the server.
        :raises RequestException: If expunging fails.
        """
        logger_imap.debug("Expunging mailbox '%s'", mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        try:
            typ, data = self.connection.expunge()
            if typ != 'OK':
                raise RequestException(f"Failed to expunge mailbox {mailbox}.")

            expunged_count = 0
            if data:
                expunged_count = len([item for item in data if item])

            logger_imap.info("Expunged %d message(s) from mailbox '%s'", expunged_count, mailbox)
            return expunged_count

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while expunging mailbox '{mailbox}': {e}") from e

    def purge_folder(self, mailbox: str, before_date: str | None = None) -> int:
        """Mark all mails in a folder as deleted (optionally before a specific date).

        This is an atomic operation that marks mails with the \\Deleted flag.
        To permanently remove them, call expunge_folder() afterward.

        :param mailbox: The name of the mailbox to purge.
        :type mailbox: str
        :param before_date: Optional date string (YYYY-MM-DD). Only mails before this date will be marked as deleted.
        :type before_date: str | None
        :return: Number of messages that were successfully marked as deleted.
        :rtype: int
        :raises RequestException: If not connected to the server or if the operation fails.
        """
        logger_imap.debug("Purging mailbox '%s' with date filter: %s", mailbox, before_date)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            # Ensure we have a concrete sequence (list) to iterate and measure
            mail_uids = list(self.get_mail_uids_before_date(mailbox, before_date, exclude_deleted=True) or [])

            if not mail_uids:
                logger_imap.info("No mails to purge in mailbox '%s'", mailbox)
                return 0

            logger_imap.info("Marking %d mail(s) as deleted in mailbox '%s'", len(mail_uids), mailbox)

            # Mark each mail as deleted using UID STORE; count successful operations
            marked_count = 0
            for mail_uid in mail_uids:
                try:
                    self.uid_store_flags(mail_uid, ['\\Deleted'], operation='+FLAGS')
                    marked_count += 1
                except RequestException as e:
                    logger_imap.warning(
                        "Failed to mark UID %s as deleted in mailbox '%s': %s", mail_uid, mailbox, e
                    )
                    # Continue with other mails even if one fails

            logger_imap.info(
                "Successfully marked %d mail(s) as deleted in mailbox '%s'", marked_count, mailbox
            )
            return marked_count

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while purging mailbox '{mailbox}': {e}") from e


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
            raise RequestException(f"IMAP select error for folder '{mailbox}': {e}") from e

        if typ != 'OK':
            raise RequestException(f"Failed to select folder {mailbox}.", err.ERROR_FOLDER_NAME_NOT_FOUND)

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

        This remains as a convenience wrapper but uses the fetch_mails_by_uids primitive.
        """
        logger_imap.debug("Fetching all full mails from '%s'", mailbox)

        if self.connection is None:
            raise RequestException("Not connected.")

        # get all UIDs then fetch them in one request
        uids = self.get_mail_uids_before_date(mailbox, None, exclude_deleted=False)
        if not uids:
            return []
        return self.fetch_mails_by_uids(mailbox, uids)

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
            typ, msg_data = self.connection.uid('FETCH', str(mail_uid), '(RFC822)')
            if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
                raise RequestException(f"Mail UID {mail_uid} not found in {mailbox}.", err.ERROR_MAIL_UID_NOT_FOUND)
            return msg_data[0][1]
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while fetching mail UID {mail_uid}: {e}", err.ERROR_MAIL_UID_NOT_FOUND) from e

    def fetch_mail_detail(self, mailbox: str, mail_uid: int) -> Dict[str, Any]:
        """Fetch a mail with additional metadata (flags, size) from a specific mailbox using UID.

        :param mailbox: The mailbox containing the mail
        :type mailbox: str
        :param mail_uid: The UID of the mail to fetch (int)
        :type mail_uid: int
        :raises RequestException: If the operation fails
        :return: A dict containing raw_message (bytes), flags (dict), and size (int)
        :rtype: Dict[str, Any]
        """
        logger_imap.debug("Fetching mail detail for UID '%s' from '%s'", mail_uid, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            # Fetch full message and FLAGS (size is included in RFC822 response)
            typ, msg_data = self.connection.uid('FETCH', str(mail_uid), '(RFC822 FLAGS)')
            if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
                raise RequestException(f"Mail UID {mail_uid} not found in {mailbox}.", err.ERROR_MAIL_UID_NOT_FOUND)

            # Parse the response
            raw_message = msg_data[0][1]

            # Extract the full response string for parsing
            response_str = msg_data[0][0].decode('utf-8', errors='ignore') if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])

            # Extract FLAGS
            flags_match = re.search(r'FLAGS \(([^)]*)\)', response_str)
            flags_list = []
            if flags_match:
                flags_str = flags_match.group(1)
                flags_list = [f.strip() for f in flags_str.split() if f.strip()]

            # Extract size from RFC822 {size} format
            size_match = re.search(r'RFC822 \{(\d+)\}', response_str)
            size = int(size_match.group(1)) if size_match else len(raw_message)

            # Parse flags into structured format
            flags_dict = {
                'seen': '\\Seen' in flags_list,
                'flagged': '\\Flagged' in flags_list,
                'answered': '\\Answered' in flags_list,
                'forwarded': '$Forwarded' in flags_list or '\\Forwarded' in flags_list,
                'all': flags_list
            }

            return {
                'raw_message': raw_message,
                'flags': flags_dict,
                'size': size
            }
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while fetching mail detail for UID {mail_uid}: {e}", err.ERROR_MAIL_UID_NOT_FOUND) from e

    def copy_mail_to_mailbox(self, mailbox: str, mail_uid: int, dest_mailbox: str) -> None:
        """Copy a mail from one mailbox to another using UID.
        Wrapper selecting mailbox then using uid_copy primitive.

        :param mailbox: The source mailbox.
        :type mailbox: str
        :param mail_uid: The UID of the mail to copy.
        :type mail_uid: int
        :param dest_mailbox: The destination mailbox.
        :type dest_mailbox: str
        :raises RequestException: If the operation fails.
        """
        logger_imap.debug("Copying mail UID '%s' from '%s' to '%s'", mail_uid, mailbox, dest_mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            self.uid_copy(mail_uid, dest_mailbox)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while copying mail UID {mail_uid}: {e}") from e

    def add_flags_to_mail(self, mailbox: str, mail_uid: int, flags: List[str]) -> None:
        """Add flags to a mail using UID.
        Wrapper selecting mailbox then using uid_store_flags primitive.

        :param mailbox: The mailbox containing the mail.
        :type mailbox: str
        :param mail_uid: The UID of the mail to modify.
        :type mail_uid: int
        :param flags: List of flags to add (e.g., ['\\Seen', '\\Flagged']).
        :type flags: List[str]
        :raises RequestException: If the operation fails.
        """
        logger_imap.debug("Adding flags %s to mail UID '%s' in '%s'", flags, mail_uid, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            self.uid_store_flags(mail_uid, flags, operation='+FLAGS')
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while adding flags to mail UID {mail_uid}: {e}") from e

    def delete_mail_by_uid(self, mailbox: str, mail_uid: int) -> None:
        """Delete a specific mail by UID (copy to Trash and mark as deleted).

        :param mailbox: The mailbox containing the mail.
        :type mailbox: str
        :param mail_uid: The UID of the mail to delete.
        :type mail_uid: int
        :raises RequestException: If the operation fails.
        """
        logger_imap.debug("Deleting mail UID '%s' from mailbox '%s'", mail_uid, mailbox)
        if self.connection is None:
            raise RequestException("Not connected.")
        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException(f"Invalid mail UID: {mail_uid}")
        try:
            # Copy mail to Trash folder
            self.uid_copy(mail_uid, "Trash")
            # Mark mail as deleted and seen
            self.uid_store_flags(mail_uid, ['\\Seen', '\\Deleted'], operation='+FLAGS')
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while deleting mail UID {mail_uid}: {e}", err.ERROR_MAIL_UID_NOT_FOUND) from e

    def get_folder_details(self, folder_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific folder.

        :param folder_name: The name of the folder to get details for.
        :type folder_name: str
        :return: Dictionary with folder details including name, path, type, flags, subscribed status, and children.
        :rtype: Dict[str, Any]
        :raises RequestException: If not connected or if the operation fails.
        """
        logger_imap.debug("Getting details for folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            # Get folder listing with attributes
            # Use '""' as reference parameter to ensure proper IMAP syntax
            typ, data = self.connection.list('""', f'"{folder_name}"')
            if typ != 'OK' or not data or not data[0]:
                raise RequestException(f"Folder '{folder_name}' not found.")

            # Parse the LIST response
            folder_info = data[0]
            folder_info_str = ""
            if isinstance(folder_info, bytes):
                folder_info_str = folder_info.decode('utf-8')
            elif isinstance(folder_info, tuple):
                # Handle tuple response
                folder_info_str = folder_info[0].decode('utf-8') if isinstance(folder_info[0], bytes) else str(folder_info[0])
            else:
                folder_info_str = str(folder_info)

            # Parse folder attributes and name from LIST response
            # Format: (\\Flags) "delimiter" "folder_name"
            attributes_match = re.search(r'\((.*?)\)', folder_info_str)
            attributes = []
            if attributes_match:
                attrs_str = attributes_match.group(1)
                attributes = [attr.strip('\\').lower() for attr in attrs_str.split() if attr]

            # Get folder name (handle quoted names)
            name_match = re.search(r'"[^"]*"\s+"([^"]+)"', folder_info_str)
            if not name_match:
                name_match = re.search(r'"[^"]*"\s+(\S+)', folder_info_str)

            parsed_name = name_match.group(1) if name_match else folder_name

            # Determine folder type based on attributes and name
            folder_type = self._determine_folder_type(parsed_name, attributes)

            # Get children folders (subfolders)
            children = self._get_folder_children(folder_name)

            # Check subscription status
            subscribed = self._is_folder_subscribed(folder_name)

            # Get message counts (unseen and total)
            message_count, unseen_count = self._get_folder_message_counts(folder_name)

            return {
                "name": parsed_name,
                "path": folder_name,
                "sievePath": folder_name,
                "type": folder_type,
                "flags": attributes,
                "subscribed": 1 if subscribed else 0,
                "unseenCount": unseen_count,
                "messageCount": message_count,
                "children": children
            }

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error getting folder details for '{folder_name}': {e}") from e

    def _determine_folder_type(self, folder_name: str, attributes: List[str]) -> str:
        """Determine the type of folder based on its name and attributes.

        :param folder_name: The name of the folder.
        :type folder_name: str
        :param attributes: List of IMAP attributes/flags.
        :type attributes: List[str]
        :return: Folder type string.
        :rtype: str
        """
        # Check special attributes first
        if 'drafts' in attributes:
            return 'draft'
        if 'sent' in attributes:
            return 'sent'
        if 'trash' in attributes:
            return 'trash'
        if 'junk' in attributes or 'spam' in attributes:
            return 'junk'

        # Check folder name patterns
        folder_lower = folder_name.lower()
        if folder_lower == 'inbox':
            return 'inbox'
        if 'draft' in folder_lower:
            return 'draft'
        if 'sent' in folder_lower:
            return 'sent'
        if 'trash' in folder_lower or 'deleted' in folder_lower:
            return 'trash'
        if 'junk' in folder_lower or 'spam' in folder_lower:
            return 'junk'
        if 'template' in folder_lower:
            return 'templates'

        return 'folder'

    def _get_folder_children(self, folder_name: str) -> List[Dict[str, Any]]:
        """Get children folders of a specific folder.

        :param folder_name: The name of the parent folder.
        :type folder_name: str
        :return: List of child folder details.
        :rtype: List[Dict[str, Any]]
        """
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            # List direct children using wildcard pattern
            # For IMAP: use "%"  to match direct children only (not recursive)
            # Reference parameter is '""' to ensure proper IMAP syntax
            if folder_name:
                pattern = f'"{folder_name}/%"'
            else:
                # For root level folders, just use "%"
                pattern = "%"

            typ, data = self.connection.list('""', pattern)

            if typ != 'OK' or not data:
                raise RequestException(f"Failed to list children for mailbox '{folder_name}' (IMAP response: {typ})")

            children = []
            for item in data:
                if not item or item == b'':
                    continue

                item_str = ""
                if isinstance(item, bytes):
                    item_str = item.decode('utf-8')
                elif isinstance(item, tuple):
                    item_str = item[0].decode('utf-8') if isinstance(item[0], bytes) else str(item[0])
                else:
                    item_str = str(item)

                # Parse attributes
                attributes_match = re.search(r'\((.*?)\)', item_str)
                attributes = []
                if attributes_match:
                    attrs_str = attributes_match.group(1)
                    attributes = [attr.strip('\\').lower() for attr in attrs_str.split() if attr]

                # Get folder name
                name_match = re.search(r'"[^"]*"\s+"([^"]+)"', item_str)
                if not name_match:
                    name_match = re.search(r'"[^"]*"\s+(\S+)', item_str)

                if name_match:
                    full_path = name_match.group(1)
                    # Get just the child name (last part after separator)
                    child_name = full_path.split('/')[-1] if '/' in full_path else full_path

                    folder_type = self._determine_folder_type(full_path, attributes)
                    subscribed = self._is_folder_subscribed(full_path)
                    message_count, unseen_count = self._get_folder_message_counts(full_path)

                    children.append({
                        "name": child_name,
                        "path": full_path,
                        "sievePath": full_path,
                        "type": folder_type,
                        "flags": attributes,
                        "subscribed": 1 if subscribed else 0,
                        "unseenCount": unseen_count,
                        "messageCount": message_count,
                        "children": []
                    })

            return children

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            #TODO: Question Quentin: Transform low level exceptions to RequestException 
            raise RequestException(f"Error getting children for folder '{folder_name}': {e}") from e

    def _get_folder_message_counts(self, folder_name: str) -> Tuple[int, int]:
        """Get the total message count and unseen message count for a folder.

        :param folder_name: The name of the folder.
        :type folder_name: str
        :return: Tuple of (message_count, unseen_count).
        :rtype: Tuple[int, int]
        """
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            # Use STATUS command to get counts without selecting the mailbox
            # This is more efficient than SELECT for just getting counts
            typ, data = self.connection.status(f'"{folder_name}"', '(MESSAGES UNSEEN)')
            
            if typ != 'OK' or not data or not data[0]:
                # Fallback: return 0, 0 if STATUS fails
                logger_imap.warning("Failed to get STATUS for folder '%s', returning 0 counts", folder_name)
                return 0, 0

            # Parse STATUS response: e.g., b'INBOX (MESSAGES 42 UNSEEN 5)'
            status_str = data[0].decode('utf-8') if isinstance(data[0], bytes) else str(data[0])
            
            message_count = 0
            unseen_count = 0
            
            # Extract MESSAGES count
            messages_match = re.search(r'MESSAGES\s+(\d+)', status_str)
            if messages_match:
                message_count = int(messages_match.group(1))
            
            # Extract UNSEEN count
            unseen_match = re.search(r'UNSEEN\s+(\d+)', status_str)
            if unseen_match:
                unseen_count = int(unseen_match.group(1))
            
            return message_count, unseen_count

        except (imaplib.IMAP4.error, OSError, socket.error, ValueError) as e:
            logger_imap.warning("Error getting message counts for folder '%s': %s, returning 0 counts", folder_name, e)
            return 0, 0

    def _is_folder_subscribed(self, folder_name: str) -> bool:
        """Check if a folder is subscribed.

        :param folder_name: The name of the folder.
        :type folder_name: str
        :return: True if subscribed, False otherwise.
        :rtype: bool
        """
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.lsub('""', f'"{folder_name}"')
            if typ == 'OK' and data and data[0]:
                return True
            if typ == 'OK':
                return False
            # if server returned an error status, surface it
            raise RequestException(f"Failed to check subscription status for '{folder_name}' (IMAP response: {typ})")
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            #TODO: Question Quentin: Transform low level exceptions to RequestException ?
            raise RequestException(f"Error checking subscription for folder '{folder_name}': {e}") from e

    def rename_folder(self, old_name: str, new_name: str) -> None:
        """Rename a folder (mailbox) on the IMAP server.

        :param old_name: The current name of the folder.
        :type old_name: str
        :param new_name: The new name for the folder.
        :type new_name: str
        :raises RequestException: If not connected to the server or if renaming fails.
        """
        logger_imap.debug("Renaming folder from '%s' to '%s'", old_name, new_name)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.rename(old_name, new_name)
            if typ != 'OK':
                error_msg = data[0].decode('utf-8') if data and isinstance(data[0], bytes) else "Unknown error"
                raise RequestException(f"Failed to rename folder from '{old_name}' to '{new_name}': {error_msg}")
            logger_imap.info("Successfully renamed folder from '%s' to '%s'", old_name, new_name)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while renaming folder from '{old_name}' to '{new_name}': {e}") from e

    def subscribe_folder(self, folder_name: str) -> None:
        """Subscribe to a folder on the IMAP server.

        :param folder_name: The name of the folder to subscribe to.
        :type folder_name: str
        :raises RequestException: If not connected to the server or if subscription fails.
        """
        logger_imap.debug("Subscribing to folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.subscribe(folder_name)
            if typ != 'OK':
                error_msg = data[0].decode('utf-8') if data and isinstance(data[0], bytes) else "Unknown error"
                raise RequestException(f"Failed to subscribe to folder '{folder_name}': {error_msg}")
            logger_imap.info("Successfully subscribed to folder '%s'", folder_name)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while subscribing to folder '{folder_name}': {e}") from e

    def unsubscribe_folder(self, folder_name: str) -> None:
        """Unsubscribe from a folder on the IMAP server.

        :param folder_name: The name of the folder to unsubscribe from.
        :type folder_name: str
        :raises RequestException: If not connected to the server or if unsubscription fails.
        """
        logger_imap.debug("Unsubscribing from folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.unsubscribe(folder_name)
            if typ != 'OK':
                error_msg = data[0].decode('utf-8') if data and isinstance(data[0], bytes) else "Unknown error"
                raise RequestException(f"Failed to unsubscribe from folder '{folder_name}': {error_msg}")
            logger_imap.info("Successfully unsubscribed from folder '%s'", folder_name)
        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while unsubscribing from folder '{folder_name}': {e}") from e

    def get_acl(self, folder_name: str) -> List[Tuple[str, Dict[str, int]]]:
        """Get the Access Control List (ACL) for a specific folder.

        Uses the IMAP GETACL command to retrieve folder permissions and converts
        them to SOGo rights format.

        :param folder_name: The name of the folder to get ACL for.
        :type folder_name: str
        :return: List of tuples (identifier, rights_dict) where identifier is a username 
                 and rights_dict is a dictionary of SOGo rights
        :rtype: List[Tuple[str, Dict[str, int]]]
        :raises RequestException: If not connected to the server or if getting ACL fails.
        """
        logger_imap.debug("Getting ACL for folder '%s'", folder_name)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.getacl(folder_name)
            if typ != 'OK':
                error_msg = data[0].decode('utf-8') if data and isinstance(data[0], bytes) else "Unknown error"
                raise RequestException(f"Failed to get ACL for folder '{folder_name}': {error_msg}")

            # Parse the response: data[0] is typically bytes like b'INBOX identifier1 rights1 identifier2 rights2 ...'
            if not data or not data[0]:
                return []

            response = data[0].decode('utf-8') if isinstance(data[0], bytes) else str(data[0])

            # Split the response: first part is folder name, rest are identifier/rights pairs
            parts = response.split()
            if len(parts) < 1:
                return []

            # Skip first part (folder name) and parse pairs
            acl_list: List[Tuple[str, Dict[str, int]]] = []
            i = 1  # Start after folder name
            while i < len(parts) - 1:
                identifier = parts[i]
                imap_rights = parts[i + 1]
                # Convert IMAP rights string to SOGo rights dictionary
                sogo_rights = _convert_imap_to_rights(imap_rights)
                acl_list.append((identifier, sogo_rights))
                i += 2

            logger_imap.debug("Retrieved ACL for folder '%s': %s", folder_name, acl_list)
            return acl_list

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while getting ACL for folder '{folder_name}': {e}") from e

    def set_acl(self, folder_name: str, identifier: str, rights: Dict[str, Any]) -> None:
        """Set ACL rights for a specific user/identifier on a folder.

        Uses the IMAP SETACL command to grant permissions. Converts SOGo rights
        dictionary to IMAP ACL string format.

        :param folder_name: The name of the folder.
        :type folder_name: str
        :param identifier: The user identifier (email, username, or special like 'anyone').
        :type identifier: str
        :param rights: Dictionary of SOGo rights (e.g., {"userCanViewFolder": 1, "userCanReadMails": 1})
        :type rights: Dict[str, Any]
        :raises RequestException: If not connected to the server or if setting ACL fails.
        """
        # Convert SOGo rights dictionary to IMAP rights string
        imap_rights = _convert_rights_to_imap(rights)

        logger_imap.debug("Setting ACL for folder '%s', identifier '%s', SOGo rights %s -> IMAP rights '%s'", 
                         folder_name, identifier, rights, imap_rights)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.setacl(folder_name, identifier, imap_rights)
            if typ != 'OK':
                error_msg = data[0].decode('utf-8') if data and isinstance(data[0], bytes) else "Unknown error"
                raise RequestException(f"Failed to set ACL for folder '{folder_name}': {error_msg}")

            logger_imap.info("Successfully set ACL for folder '%s', identifier '%s', IMAP rights '%s'", 
                           folder_name, identifier, imap_rights)

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while setting ACL for folder '{folder_name}': {e}") from e

    def delete_acl(self, folder_name: str, identifier: str) -> None:
        """Delete ACL rights for a specific user/identifier on a folder.

        Uses the IMAP DELETEACL command to remove all permissions for an identifier.

        :param folder_name: The name of the folder.
        :type folder_name: str
        :param identifier: The user identifier to remove ACL for.
        :type identifier: str
        :raises RequestException: If not connected to the server or if deleting ACL fails.
        """
        logger_imap.debug("Deleting ACL for folder '%s', identifier '%s'", folder_name, identifier)
        if self.connection is None:
            raise RequestException("Not connected.")

        try:
            typ, data = self.connection.deleteacl(folder_name, identifier)
            if typ != 'OK':
                error_msg = data[0].decode('utf-8') if data and isinstance(data[0], bytes) else "Unknown error"
                raise RequestException(f"Failed to delete ACL for folder '{folder_name}': {error_msg}")

            logger_imap.info("Successfully deleted ACL for folder '%s', identifier '%s'", folder_name, identifier)

        except (imaplib.IMAP4.error, OSError, socket.error) as e:
            raise RequestException(f"Error while deleting ACL for folder '{folder_name}': {e}") from e

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