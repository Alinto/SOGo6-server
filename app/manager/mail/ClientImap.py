from __future__ import annotations
from typing import Any, Callable, TypeVar, ParamSpec, Iterator

from email import message_from_bytes
import imaplib
import re
from datetime import datetime
from socket import timeout as sock_timeout, gaierror
from ssl import SSLError

from app.utils.exceptions import AggravatedException, RequestException, BugException
from app.utils.logger.logger import logger_imap
from app.manager.mail.ClientMailServer import ClientMailServer
from app.utils import errors as err
from app.utils import constants as cs
from app.utils.strings import quote, imap_join_folders

# Maximum debug output from imaplib
#TODO link this to the admin param for mail server log
#TODO all imap are logged, including login/auth password...
imaplib.Debug = 4  # type: ignore[attr-defined]

P = ParamSpec("P")
R = TypeVar("R")

# IMAP ACL rights conversion utilities
# Mapping constants to centralize conversions between SOGo rights and IMAP ACL chars.
RIGHTS_MAP: dict[str, str] = {
    cs.USER_CAN_VIEW_FOLDER: "lr",            # lookup + read
    cs.USER_CAN_READ_MAILS: "s",              # keep seen/unseen information (s)
    cs.USER_CAN_MARK_MAILS_READ: "w",          # write (w)
    cs.USER_CAN_INSERT_MAILS: "i",            # insert (i)
    cs.USER_CAN_POST_MAILS: "p",              # post (p)
    cs.USER_CAN_CREATE_SUBFOLDERS: "k",       # create subfolders (k) (c is obsolete/alias)
    cs.USER_CAN_REMOVE_FOLDER: "x",           # delete mailbox (x)
    cs.USER_CAN_ERASE_MAILS: "t",             # delete messages (t)
    cs.USER_CAN_EXPUNGE_FOLDER: "e",          # expunge (e)
    cs.USER_CAN_WRITE_EMAILS: "w",             # same as mark mails read/write flags
    cs.USER_CAN_ADMINISTRATOR: "a",          # administer (a)
}

# IMAP char -> list of SOGo keys to set when char present.
IMAP_TO_SOGO: dict[str, list[str]] = {
    "s": [cs.USER_CAN_READ_MAILS],
    "w": [cs.USER_CAN_MARK_MAILS_READ, cs.USER_CAN_WRITE_EMAILS],
    "i": [cs.USER_CAN_INSERT_MAILS],
    "p": [cs.USER_CAN_POST_MAILS],
    "k": [cs.USER_CAN_CREATE_SUBFOLDERS],
    "c": [cs.USER_CAN_CREATE_SUBFOLDERS],  # obsolete alias for create
    "x": [cs.USER_CAN_REMOVE_FOLDER],
    "t": [cs.USER_CAN_ERASE_MAILS],
    "e": [cs.USER_CAN_EXPUNGE_FOLDER],
    "d": [cs.USER_CAN_REMOVE_FOLDER, cs.USER_CAN_ERASE_MAILS, cs.USER_CAN_EXPUNGE_FOLDER],  # obsolete -> x+t+e
    "a": [cs.USER_CAN_ADMINISTRATOR],
}

def _convert_rights_to_imap(rights_dict: dict[str, Any]) -> str:
    """Convert SOGo rights dictionary to IMAP ACL rights string using RIGHTS_MAP.

    Preserves order defined in RIGHTS_MAP and removes duplicates.
    
    :param rights_dict: dictionary of SOGo rights (keys like "userCanViewFolder", values are truthy/falsy)
    :type rights_dict: dict[str, Any]
    :return: IMAP ACL rights string (e.g., "lrswipkxtea")
    :rtype: str
    """

    imap_chars: list[str] = []
    seen = set()

    for sogo_key, imap_seq in RIGHTS_MAP.items():
        if rights_dict.get(sogo_key):
            for ch in imap_seq:
                if ch not in seen:
                    seen.add(ch)
                    imap_chars.append(ch)

    return "".join(imap_chars)


def _convert_imap_to_rights(imap_rights: str) -> dict[str, int]:
    """Convert IMAP ACL rights string to SOGo rights dictionary using IMAP_TO_SOGO.

    Behaviours preserved:
    - userCanViewFolder is set only when both 'l' and 'r' present.
    - 'd' expands to x,t,e as before.
    
    :param imap_rights: IMAP ACL rights string (e.g., "lrswipkxtea")
    :type imap_rights: str
    :return: dictionary of SOGo rights with integer values (0 or 1)
    :rtype: dict[str, int]
    """
    # Initialize all rights to 0
    #TODO refactor folder acl, too much details for commoner.
    sogo_rights: dict[str, int] = {
        cs.USER_CAN_VIEW_FOLDER: 0,
        cs.USER_CAN_READ_MAILS: 0,
        cs.USER_CAN_MARK_MAILS_READ: 0,
        cs.USER_CAN_INSERT_MAILS: 0,
        cs.USER_CAN_POST_MAILS: 0,
        cs.USER_CAN_CREATE_SUBFOLDERS: 0,
        cs.USER_CAN_REMOVE_FOLDER: 0,
        cs.USER_CAN_ERASE_MAILS: 0,
        cs.USER_CAN_EXPUNGE_FOLDER: 0,
        cs.USER_CAN_WRITE_EMAILS: 0,
        cs.USER_CAN_ADMINISTRATOR: 0
    }

    rights_lower = imap_rights.lower()

    # Track presence of 'l' and 'r' for userCanViewFolder
    has_l = 'l' in rights_lower
    has_r = 'r' in rights_lower

    # Set flags based on IMAP_TO_SOGO mapping
    for ch in rights_lower:
        if sogo_keys := IMAP_TO_SOGO.get(ch, None):
            for key in sogo_keys:
                sogo_rights[key] = 1
        else:
            logger_imap.error("Unexpected acl letter: %s", ch)
            raise BugException(f"Unexpected acl letter: {ch}")

    # Now handle l+r -> userCanViewFolder (must have both)
    if has_l and has_r:
        sogo_rights[cs.USER_CAN_VIEW_FOLDER] = 1

    return sogo_rights

class ImapFolder:
    """
    Simple class to parse folder response and store useful values
    """
    def __init__(self) -> None:
        self.name = ""
        self.path = ""
        self.parent = ""
        self.can_be_select = True
        self.has_subfolder = False
        self.can_set_subfolder = True
        self.flags: list[str] = []
        self.delimiter = ""
        self.type: str = cs.MAIL_FOLDER_NORMAL

        #May not be set
        self.is_subscribed: bool|None = None
        self.nb_mails: int|None = None
        self.nb_unseen: int|None = None


    def init_from_list_response(self, response:str, folder_name_to_type: dict) -> None:
        """
        https://datatracker.ietf.org/doc/html/rfc9051#name-list-command-examples
        '(\\flag1 \\flag2) "." name (optional options)'
        or
        '() "." "name with space" (optional options)'

        flags detailed here: https://datatracker.ietf.org/doc/html/rfc9051#name-list-response

        :param response: raw response of the command list
        :type response: str
        """
        # Extract flags
        flags_match = re.search(r'\((.*?)\)', response)
        if flags_match:
            self.flags = flags_match.group(1).split()
        if self.flags:
            self.has_subfolder = "\\HasChildren" in self.flags
            self.can_be_select = not ("\\NonExistent" in self.flags or "\\Noselect" in self.flags)
            self.can_set_subfolder = "\\Noinferiors" not in self.flags
            self.is_subscribed = "\\Subscribed" in self.flags

        #Extract delimiter and path
        delimiter_name_match = re.search(r'"(.*?)"\s+(?:"(.*?)"|(\S+))', response)
        if delimiter_name_match:
            self.delimiter = delimiter_name_match.group(1)
            self.path = delimiter_name_match.group(2) or delimiter_name_match.group(3)

        #Check parent
        if self.delimiter and self.delimiter in self.path:
            self.parent, self.name = self.path.rsplit(self.delimiter, 1)
        else:
            self.name = self.path

        #Check type
        self.type =  folder_name_to_type.get(self.path, cs.MAIL_FOLDER_NORMAL)

    def init_from_list_extended_response(self, response_list:str, response_status:str, folder_name_to_type: dict) -> None:
        """
        Same as init_from_list_response but with status too
        'xyz (MESSAGES 25 UNSEEN 12)'
        '"Junk Email" (MESSAGES 0 UNSEEN 0)'

        """
        self.init_from_list_response(response_list, folder_name_to_type)

        #Check status
        match = re.search(r"MESSAGES\s+(\d+).*?UNSEEN\s+(\d+)", response_status)
        if match:
            self.nb_mails = int(match.group(1))
            self.nb_unseen = int(match.group(2))

    def __repr__(self) -> str:
        return str({
            "name": self.name,
            "path": self.path,
            "parent": self.parent,
            "can_be_select": self.can_be_select,
            "has_subfolder": self.has_subfolder,
            "can_set_subfolder": self.can_set_subfolder,
            "flags": self.flags,
            "delimiter": self.delimiter,
            "type": self.type,
            "is_subscribed": self.is_subscribed,
            "nb_mails": self.nb_mails,
            "nb_unseen": self.nb_unseen
        })


def parse_uids_from_bytes(byte_data: bytes) -> Iterator[str]:
    """
    IMAP can answer long list of bytes in this format
    b'1 2 3 4 5 6 7 8 9 10'
    This bytes can be very long (like 10k mail's uid).

    To avoid loading all this in memory by using split,
    this method parse them, decode them and yield them one by one

    :param byte_data: byte array of uids
    :type byte_data: bytes
    :yield: uid sting one by one
    :rtype: Iterator[str]
    """
    current_uid: list[bytes] = []
    for byte in byte_data:
        if byte == b' ':
            if current_uid:  # Avoid yielding empty strings
                yield b''.join(current_uid).decode('utf-8')
                current_uid = []
        else:
            current_uid.append(bytes([byte]))
    if current_uid:  # Yield the last UID if there's no trailing space
        yield b''.join(current_uid).decode('utf-8')


class ClientImap(ClientMailServer):
    """
    IMAP client implementation for Dovecot using imaplib.
    """

    def __init__(self, server: str, port: int, encryption: str, auth_mech: str, folders_map: dict) -> None:
        """
        Initialize the IMAP client.

        folders_map is a dict that map folder type (inbox, sent, ...) to the folder name
        """
        super().__init__()
        self.server = server
        self.port   = port
        self.encryption = encryption
        self.auth_mech  = auth_mech
        self.folders_map_type_to_name = folders_map
        self.folders_map_name_to_type = {v: k for k, v in folders_map.items()}
        if len(self.folders_map_type_to_name) != len(self.folders_map_name_to_type):
            raise BugException("Two or more folders types have the same name", err.ERROR_CONFIG_ERROR)

        self.connection: imaplib.IMAP4 | None = None

        #Set after connection
        self.capabilities: set[str] = set()

        #Set after authentication
        self.default_delimiter: str = ""
        self.default_prefix: str = ""
        self.others_prefixes: dict = {} # dict of {"prefix": "delimiter"}

    def connect(self) -> None:
        """
        Connect to the IMAP sImapFoldererver according to the encryption.
        Also get the capabilities of the server
        """
        try:
            if self.encryption == cs.SOCKET_ENC_PLAIN:
                self.connection = imaplib.IMAP4(self.server, self.port)

            elif self.encryption == cs.SOCKET_ENC_EXPLICIT_TLS:
                self.connection = imaplib.IMAP4(self.server, self.port)
                self.connection.starttls()

            elif self.encryption == cs.SOCKET_ENC_IMPLICIT_TLS:
                self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                raise BugException(f"Unknown encryption given {self.encryption}")
            self.connected = True

            logger_imap.info("Successfully connected to IMAP server %s:%d", self.server, self.port)
        except (gaierror, sock_timeout, TimeoutError, ConnectionRefusedError, imaplib.IMAP4.error, SSLError) as e:
            logger_imap.error("IMAP connection error to %s:%d - %s", self.server, self.port, e)
            raise RequestException(f"IMAP connection error: {e}", err.ERROR_IMAP_CONNECTION_FAILED) from e

    def _exec_imap4_method(self, imap4_method: Callable[P, tuple[str, list]], *args: P.args, **kwargs: P.kwargs) -> tuple[bool, list[bytes]]:
        """
        IMAP4 (and IMAP4_SSL) raise a lot of exception:
        class error(Exception): pass    # Logical errors - debug required
        class abort(error): pass        # Service errors - close and retry
        class readonly(abort): pass     # Mailbox status changed to READ-ONLY

        To avoid writting try/except block each time a IMAP4 method is called,
        we call them with this function that will return a proper, consitant
        tuple

        :param imap4_method: IMAP4 method to call
        :type imap4_method: Callable[P, R]
        :raises RequestException: If the service is unavailable
        :return: True if command succedeed with associate data, False with list of errors
        :rtype: tuple[bool, list[bytes]]
        """
        try:
            typ, data = imap4_method(*args, **kwargs)
            #logger_imap.debug("imap4_exec: (%s,%s)", typ, data)
            if typ not in {'NO', 'BAD'}:
                if len(data) == 1 and not data[0]:
                    # return an empty list instead
                    data = []
                return True, data
            return False, data
        except imaplib.IMAP4.readonly as e:
            raise BugException(err.ERROR_IMAP_READONLY.m, err.ERROR_IMAP_READONLY) from e
        except imaplib.IMAP4.abort as e:
            raise RequestException(err.ERROR_IMAP_UNAIVALABLE.m, err.ERROR_IMAP_UNAIVALABLE) from e
        except imaplib.IMAP4.error as e:
            # e.args is a tuple of bytes
            logger_imap.warning("IMAP command returns this error %s", e)
            return False, list(e.args)

    def login(self, username: str, password: str, authname: str = "") -> None:
        """Login to the IMAP server according to SOGO_D_IMAP_AUTH_MECH

        :param username: The username for authentication.
        :type username: str
        :param password: The password/token/creds for authentication
        :type password: str
        :raises RequestException: If login fails.
        """
        logger_imap.info("Logging in as %s using auth_mech=%s", username, self.auth_mech)
        if self.connection is not None:
            if self.connection.state != "NONAUTH":
                if self.connection.state == "LOGOUT":
                    #Never in the code should we make a login command after a logout, a problem of logic/process here
                    raise BugException(err.ERROR_IMAP_LOGOUT.m, err.ERROR_IMAP_LOGOUT)
                logger_imap.debug("Already Authenticated")
                self.authenticated = True
                return

            if self.auth_mech == "login":
                success, datas = self._exec_imap4_method(self.connection.login, username, password)
            elif self.auth_mech in ("plain", "xoauth2", "oauthbearer"):
                if not authname:
                    authname = username
                conn_by_mech = {
                    "plain": lambda _: f"{authname}\0{username}\0{password}",
                    "xoauth2": lambda _: f"user={username}\x01auth=Bearer {password}\x01\x01",
                    "oauthbearer": lambda _: f"n,a={username},\x01host={self.server}\x01port={self.port}\x01auth=Bearer {password}\x01\x01"
                }
                # The ignores comments are here because mypy is drunk and don't know what IMAP4.authenticate expects or returns
                success, datas = self._exec_imap4_method(self.connection.authenticate, # type: ignore [arg-type]
                                                         self.auth_mech.upper(),
                                                         conn_by_mech[self.auth_mech]) # type: ignore [arg-type]
            else:
                raise BugException(f"Unsupported imap authentication mechanism: {self.auth_mech}", err.ERROR_IMAP_UNKNWON_AUTH_MECH)
            if not success:
                #errors are in datas
                if datas[0].decode().startswith("[AUTHENTICATIONFAILED]"):
                    raise RequestException(f"Failed to login to IMAP server: {datas} ", err.ERROR_IMAP_UNAUTHORIZED)
                logger_imap.error("Cannot login to IMAP server: %s", datas)
                raise RequestException(f"Cannot login to IMAP server: {datas}", err.ERROR_IMAP_FAILED)
            self.authenticated = True

            #Get capabilities
            capabilities: bytes = self.connection.response('CAPABILITY')[1][0]
            self.capabilities = set(capabilities.decode().split())

            #Get namespace
            self.namespace()
        else:
            raise BugException("self.connection is still None, meaning self.connect() method didn't catch or raise correctly an error")

    def namespace(self) -> None:
        """
        Request the namespaces accessible for this user
        https://datatracker.ietf.org/doc/html/rfc9051#section-6.3.10

        There is a lot to say about namespace but what we want here is to
        get the delimiter for the associated prefix.

        :raises RequestException: _description_
        :raises BugException: _description_
        """
        if self.connection is not None and self.authenticated:
            success, datas = self._exec_imap4_method(self.connection.namespace)
            if not success:
                raise RequestException("Failed to list mailboxes", err.ERROR_IMAP_FAILED)

            def _extract_namespace(namespace_str:str, is_default:bool = False) -> None:
                """
                A imap namespace response is either 'NIL' or
                '(("prefix1" "delimiter1" "extra_param_optionnal")("prefix2" "delimiter2"))
                """
                if namespace_str == "NIL":
                    return None
                ##Removing the first '((' and last '))', then split ')('
                namespace_list = namespace_str[2:-2].split(")(")
                for idx, namespace in enumerate(namespace_list):
                    _, prefix, _, delimiter, *_ = namespace.split('"')
                    if is_default and idx == 0:
                        self.default_prefix = prefix
                        self.default_delimiter = delimiter
                    else:
                        if not prefix:
                            prefix = cs.IMAP_DEFAULT_DELIMITER
                        self.others_prefixes[prefix] = delimiter
                return None

            for idx, namespaces in enumerate(re.findall(r'\(\(.*?\)\)', datas[0].decode())):
                _extract_namespace(namespaces, idx == 0)
            print(f"NAMESPACE: default: ({self.default_prefix} {self.default_delimiter}) and others: {self.others_prefixes}")
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def _get_delimiter_for(self, folder_path:str) -> str:
        """
        Return the delimiter for this folder path
        """
        for prefix, delimiter in self.others_prefixes.items():
            if folder_path.startswith(prefix):
                return delimiter
        return self.default_delimiter


#########
#FOLDERS#
#########

    def _imap_list_folders(self, folder_path: str = '"*"') -> Iterator[ImapFolder]:
        """
        Simply list all mailboxes (folders) and yield the decoded result
        https://datatracker.ietf.org/doc/html/rfc9051#name-list-response
        '(\\attr1 \\attr2) "." name (optional extended field)'

        We use the LIXT-EXTENDED and LIST-STATUS to only make one request
        https://www.iana.org/assignments/imap-list-extended/imap-list-extended.xhtml
        
        :param folder_path: The name of the specific folder to list. Leave empty to list all.
        :type folder_path: str, Optionnal 
        :raises RequestException: If not connected to the server.
        :raises RequestException: If listing mailboxes fails.
        :return: A list of mailbox names.
        :rtype: list[bytes]
        """
        if self.connection is not None and self.authenticated:
            datas_status: list[bytes] = []
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            if {"LIST-EXTENDED", "LIST-STATUS"}.issubset(self.capabilities):
                success, _ = self._exec_imap4_method(self.connection.xatom,\
                                                         "LIST", '""', folder_path, 'RETURN (STATUS (MESSAGES UNSEEN) SUBSCRIBED CHILDREN)')
                if not success:
                    raise RequestException("Failed to list mailboxes", err.ERROR_IMAP_FAILED)
                if success:
                    success_list, datas_list = self._exec_imap4_method(self.connection.response, 'LIST')
                    if not success_list:
                        raise RequestException(f"Failed to list mailboxes: {datas_list}", err.ERROR_IMAP_FAILED)
                    success_status, datas_status = self._exec_imap4_method(self.connection.response, 'STATUS')
                    if not success_status:
                        raise RequestException(f"Failed to status mailboxes: {datas_status}", err.ERROR_IMAP_FAILED)
                    for data_list, data_status in zip(datas_list, datas_status):
                        folder = ImapFolder()
                        folder.init_from_list_extended_response(data_list.decode(), data_status.decode(), self.folders_map_name_to_type)
                        yield folder
            else:
                success, datas = self._exec_imap4_method(self.connection.list, '""', folder_path)
                if not success:
                    raise RequestException(f"Failed to list mailboxes: {datas}", err.ERROR_IMAP_FAILED)
                for data in datas:
                    folder = ImapFolder()
                    folder.init_from_list_response(data.decode(), self.folders_map_name_to_type)
                    yield folder
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def list_folders(self) -> list[dict[str, Any]]:
        """list all mailboxes with detailed information including children.

        This method retrieves all top-level folders and their complete hierarchy
        with detailed information for each folder including message counts, subscriptions, etc.

        :raises RequestException: If not connected to the server.
        :raises RequestException: If listing mailboxes fails.
        :return: A list of folder dictionaries with full details and nested children.
        :rtype: list[dict[str, Any]]
        """
        if self.connection is not None and self.authenticated:
            # list all folders at once
            children_to_adopt: dict[str, list[dict]] = {}
            all_folders: dict[str, dict] = {}
            for folder in self._imap_list_folders():
                # Check subscription status
                print(folder)
                if folder.is_subscribed is None:
                    folder.is_subscribed = self._is_folder_subscribed(folder.path)

                # Get message counts (unseen and total)
                if folder.nb_mails is None or folder.nb_unseen is None:
                    folder.nb_mails, folder.nb_unseen = self._get_folder_message_counts(folder.path)
                
                url_path = folder.path
                if folder.delimiter != ".":
                    url_path = folder.path.replace(folder.delimiter, ".")

                folder_details: dict[str, Any] = {
                    cs.FOLDER_NAME: folder.name,
                    cs.FOLDER_PATH: folder.path,
                    cs.FOLDER_URL_PATH: url_path,
                    cs.FOLDER_FILTER_PATH: folder.path,
                    cs.FOLDER_DELIMITER: folder.delimiter,
                    cs.FOLDER_TYPE: folder.type,
                    cs.FOLDER_FLAGS: folder.flags,
                    cs.FOLDER_CHILDREN: [],
                    cs.FOLDER_SELECTABLE: folder.can_be_select,
                    cs.FOLDER_SUSBCRIBED: int(folder.is_subscribed),
                    cs.FOLDER_UNSEEN: folder.nb_unseen,
                    cs.FOLDER_COUNT: folder.nb_mails
                }

                #Check if children were already proccessed and are waiting
                if folder.has_subfolder:
                    children = children_to_adopt.pop(folder.path, [])
                    if children:
                        folder_details["children"] = children

                #If has a parent, check if it was already proccesssed
                if folder.parent:
                    #Check if parent has already been processed
                    if folder.parent in all_folders:
                        #If yes, simply add it to the list
                        parent_folder_children:list = all_folders[folder.parent]["children"]
                        parent_folder_children.append(folder_details)
                    else:
                        #If not, update the children to adopt dict that will be used when it the folder parent turn
                        if folder.parent in children_to_adopt:
                            children_to_adopt[folder.parent] += [folder_details]
                        else:
                            children_to_adopt[folder.parent] = [folder_details]
                else:
                    all_folders[folder.path] = folder_details

            return list(all_folders.values())
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def _imap_create_folder(self, folder_path: str, auto_sub:bool = True, no_error_if_exist:bool = False) -> None:
        """
        Create a new folder (mailbox) on the IMAP server.

        :param folder_path: The name of the folder to create.
        :type folder_path: str
        :raises RequestException: If folder creation fails.
        """
        logger_imap.debug("Creating folder '%s'", folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)

            success, datas = self._exec_imap4_method(self.connection.create, folder_path)
            if not success:
                if datas[0].decode().startswith("[ALREADYEXISTS]"):
                    if no_error_if_exist:
                        return None
                    raise RequestException(f"Folder '{folder_path}' already exist", err.ERROR_FOLDER_ALREADY_EXIST)
                raise RequestException(f"Failed to create folder '{folder_path}': {datas}.", err.ERROR_IMAP_FAILED)
            if auto_sub:
                self.subscribe_folder(folder_path)
            return None
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def create_folder(self, folder_name: str, parent_path:str = "", auto_sub:bool = True) -> str:
        """
        Create a new folder (mailbox) on the IMAP server.

        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :raises RequestException: If folder creation fails.
        """
        logger_imap.debug("Creating folder '%s'", folder_name)
        if parent_path:
            delimiter = self._get_delimiter_for(parent_path)
            new_folder_path = f"{parent_path}{delimiter}{folder_name}"
        else:
            delimiter = self._get_delimiter_for(folder_name)
            new_folder_path = folder_name
        new_folder_path = quote(new_folder_path)
        if delimiter in folder_name:
            raise RequestException("Cannot create a folder whose name contains the delimiter", err.ERROR_FOLDER_DELIMITER)
        self._imap_create_folder(new_folder_path, auto_sub)
        return new_folder_path

    def _fix_folder_path(self, folder_path: str) -> str:
        """
        Some check for folder_path:
        - Check if it's ascii
        - UI will always use '.' as delimiter. Because other char could break the url endpoint
        Replace with the correct delimiter.

        :param folder_path: _description_
        :type folder_path: str
        :return: _description_
        :rtype: str
        """
        if not folder_path.isascii():
            raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)

        #Careful, UI will always use '.' as de limiter. Because other char could break the url endpoint
        #Replace with the correct delimiter
        if "." in folder_path:
            delimiter = self._get_delimiter_for(folder_path.split(".")[0])
            if delimiter != ".":
                folder_path = folder_path.replace(".", delimiter)

        return folder_path

    def get_one_folder(self, folder_path: str) -> dict[str, Any]:
        """
        Get info on one folder
        """
        if self.connection is not None and self.authenticated:
            folder_path = quote(self._fix_folder_path(folder_path))

            folders = list(self._imap_list_folders(folder_path))
            if len(folders) > 1:
                raise RequestException(f"List of {folder_path} returns more than on result", err.ERROR_FOLDER_NOT_UNIQUE)
            if len(folders) == 0:
                raise RequestException(f"List of {folder_path} returns no result", err.ERROR_FOLDER_NAME_NOT_FOUND)

            folder = folders[0]
            if folder.is_subscribed is None:
                folder.is_subscribed = self._is_folder_subscribed(folder.path)

            # Get message counts (unseen and total)
            if folder.nb_mails is None or folder.nb_unseen is None:
                folder.nb_mails, folder.nb_unseen = self._get_folder_message_counts(folder.path)

            url_path = folder.path
            if folder.delimiter != ".":
                url_path = folder.path.replace(folder.delimiter, ".")

            return {
                    cs.FOLDER_NAME: folder.name,
                    cs.FOLDER_PATH: folder.path,
                    cs.FOLDER_URL_PATH: url_path,
                    cs.FOLDER_FILTER_PATH: folder.path,
                    cs.FOLDER_DELIMITER: folder.delimiter, 
                    cs.FOLDER_TYPE: folder.type,
                    cs.FOLDER_FLAGS: folder.flags,
                    cs.FOLDER_CHILDREN: [],
                    cs.FOLDER_SELECTABLE: folder.can_be_select,
                    cs.FOLDER_SUSBCRIBED: int(folder.is_subscribed),
                    cs.FOLDER_UNSEEN: folder.nb_unseen,
                    cs.FOLDER_COUNT: folder.nb_mails
                }
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def _imap_delete(self, folder_path:str, delimiter:str, do_children:bool = True) -> None:
        """
        Delete imap folder

        :param folder_path: Path fo the folder to delete
        :type folder_path: str
        :param delimiter: delimiter for this folder
        :type delimiter: str
        :param do_children: Delete the children too, defaults to True
        :type do_children: bool, optional
        :raises RequestException: If any failure
        """
        if self.connection is not None and self.authenticated:
            if do_children:
                #List all subfolders within it
                pattern_folder_path = quote(f"{folder_path}{delimiter}*")
                for folder in self._imap_list_folders(pattern_folder_path):
                    self._exec_imap4_method(self.connection.delete, folder.path)
            quoted_folder_path = quote(folder_path)
            success, _ = self._exec_imap4_method(self.connection.delete, quoted_folder_path)
            if not success:
                raise RequestException(f"Failed to delete folder '{folder_path}' or one of its children", err.ERROR_IMAP_FAILED)

    def _imap_move_folder_to_trash(self, folder_path:str, delimiter:str, do_children:bool = True) -> None:
        """
        Move a folder (meaning rename in imap) to the trash folders

        :param folder_path: Path fo the folder to move
        :type folder_path: str
        :param delimiter: delimiter for this folder
        :type delimiter: str
        :param do_children: Delete the children too, defaults to True
        :type do_children: bool, optional
        :raises RequestException: If any failure
        """
        if self.connection is not None and self.authenticated:
            folder_trash_path = self.folders_map_type_to_name[cs.MAIL_FOLDER_TRASH]
            #Ensure that trash folder exist:
            self._imap_create_folder(folder_path=folder_trash_path, no_error_if_exist=True)
            if do_children:
            #List all subfolders within it
                pattern_folder_path = quote(f"{folder_path}{delimiter}*")
                for folder in self._imap_list_folders(pattern_folder_path):
                    new_folder_path = imap_join_folders(delimiter, folder_trash_path, folder.path)
                    self._exec_imap4_method(self.connection.rename, folder.path, new_folder_path)
            new_folder_path = imap_join_folders(delimiter, folder_trash_path, folder_path)
            quoted_folder_path = quote(folder_path)
            success, _ = self._exec_imap4_method(self.connection.rename, quoted_folder_path, new_folder_path)
            if not success:
                raise RequestException(f"Failed to moving folder to trash '{folder_path}' or one of its children", err.ERROR_IMAP_FAILED)

    def delete_folder(self, folder_path: str, do_children:bool = True) -> None:
        """
        Delete a folder (mailbox) from the IMAP server.

        Two possibilities:
        If the folder is already in the trash, simply delete it
        If the folder is not in the trash

        :param folder_path: The name of the folder to delete.
        :type folder_path: str
        :raises RequestException: If folder deletion fails.
        """
        logger_imap.debug("Deleting folder '%s'", folder_path)
        if self.connection is not None and self.authenticated:
            folder_path = self._fix_folder_path(folder_path)

            delimiter = self._get_delimiter_for(folder_path)
            if folder_path.startswith(self.folders_map_type_to_name[cs.MAIL_FOLDER_TRASH]):
                self._imap_delete(folder_path, delimiter, do_children)
            else:
                #If not in trash, rename it to be trash children
                self._imap_move_folder_to_trash(folder_path, delimiter, do_children)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def rename_folder(self, old_name: str, new_name: str) -> None:
        """Rename a folder (mailbox) on the IMAP server.

        :param old_name: The current name of the folder.
        :type old_name: str
        :param new_name: The new name for the folder.
        :type new_name: str
        :raises RequestException: If not connected to the server or if renaming fails.
        """
        logger_imap.debug("Renaming folder from '%s' to '%s'", old_name, new_name)
        if self.connection is not None and self.authenticated:
            if not old_name.isascii() or not new_name.isascii():
                raise RequestException(f"Mailbox name is not ascii: {old_name} and/or {new_name}", err.ERROR_IMAP_NOT_ASCII)
            old_name = quote(old_name)
            new_name = quote(new_name)

            success, datas = self._exec_imap4_method(self.connection.rename, old_name, new_name)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{old_name}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                if datas[0].decode().startswith("[CANNOT] Renaming"):
                    raise RequestException(f"Folder '{old_name}' cannot be renamed", err.ERROR_FOLDER_CANNOT_RENAME)
                if datas[0].decode().startswith("[ALREADYEXISTS]"):
                    raise RequestException(f"Folder '{new_name}' already exist", err.ERROR_FOLDER_ALREADY_EXIST)
                raise RequestException(f"Failed to rename {old_name}", err.ERROR_IMAP_FAILED)
            logger_imap.info("Successfully renamed folder from '%s' to '%s'", old_name, new_name)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def expunge_folder(self, folder_path: str, do_children: bool = True) -> int:
        """Expunge all deleted messages in the specified mailbox.

        :param mailbox: The name listof the mailbox to expunge.
        :type mailbox: str
        :return: The number of messages that were expunged (permanently deleted).
        :rtype: int
        :raises RequestException: If not connected to the server.
        :raises RequestException: If expunging fails.
        """
        logger_imap.debug("Expunging mailbox '%s'", folder_path)
        if self.connection is not None and self.authenticated:
            folder_path = self._fix_folder_path(folder_path)

            expunged_count = 0
            if do_children:
            #List all subfolders within it
                delimiter = self._get_delimiter_for(folder_path)
                pattern_folder_path = quote(f"{folder_path}{delimiter}*")
                for folder in self._imap_list_folders(pattern_folder_path):
                    expunged_count += self.expunge_folder(folder.path, do_children=False)

            folder_path = quote(folder_path)
            self.select_mailbox(folder_path)
            success, datas = self.connection.expunge()
            if not success:
                raise RequestException(f"Failed to expunge mailbox {folder_path}", err.ERROR_IMAP_FAILED)
            expunged_count += len(datas)

            logger_imap.info("Expunge %d message(s) from mailbox '%s'", expunged_count, folder_path)
            return expunged_count
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")


    def purge_folder(self, folder_path: str, before_date: str = "", do_children: bool = True, permanently: bool = False) -> int:
        """Mark all mails in a folder as deleted (optionally before a specific date).

        This is an atomic operation that marks mails with the \\Deleted flag.
        To permanently remove them, call expunge_folder() afterward.

        :param folder_path: The name of the folder to purge.
        :type folder_path: str
        :param before_date: Optional date string (YYYY-MM-DD). Only mails before this date will be marked as deleted.
        :type before_date: str | None
        :return: Number of messages that were successfully marked as deleted.
        :rtype: int
        :raises RequestException: If not connected to the server or if the operation fails.
        """
        logger_imap.debug("Purging mailbox '%s' with date filter: %s", folder_path, before_date)
        if self.connection is not None and self.authenticated:
            folder_path = self._fix_folder_path(folder_path)

            nb_mails = 0
            if do_children:
            #List all subfolders within it
                delimiter = self._get_delimiter_for(folder_path)
                pattern_folder_path = quote(f"{folder_path}{delimiter}*")
                for folder in self._imap_list_folders(pattern_folder_path):
                    nb_mails += self.purge_folder(folder.path, before_date, do_children=False, permanently=permanently)

            # Mark each mail as deleted using UID STORE; count successful operations
            folder_path = quote(folder_path)
            self.select_mailbox(folder_path)
            mail_uid_iter = self.get_mail_uids_before_date(folder_path, before_date, exclude_deleted=True)
            nb_mails += self.uid_store_flags(mail_uid_iter, ['\\Deleted'], operation='+FLAGS')

            if permanently:
                #expunge the folders
                self.expunge_folder(folder_path)
            return nb_mails
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")


    def _is_folder_subscribed(self, folder_path: str) -> bool:
        """Check if a folder is subscribed.

        :param folder_path: The name of the folder.
        :type folder_path: str
        :return: True if subscribed, False otherwise.
        :rtype: bool
        """
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)

            success, datas = self._exec_imap4_method(self.connection.lsub, '""', folder_path)
            if success:
                #If datas is empty, it means the folder is not subscribed
                return bool(datas)
            # if server returned an error status, surface it
            raise RequestException(f"Failed to check subscription status for '{folder_path}' (IMAP response: {datas})")
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def subscribe_folder(self, folder_path: str) -> None:
        """Subscribe to a folder on the IMAP server.

        :param folder_path: The name of the folder to subscribe to.
        :type folder_path: str
        :raises RequestException: If not connected to the server or if subscription fails.
        """
        logger_imap.debug("Subscribing to folder '%s'", folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)

            success, datas = self._exec_imap4_method(self.connection.subscribe, folder_path)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{folder_path}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                raise RequestException(f"Failed to subscribe to {folder_path}", err.ERROR_IMAP_FAILED)
            logger_imap.info("Successfully subscribe to folder '%s'", folder_path)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def unsubscribe_folder(self, folder_path: str) -> None:
        """Unsubscribe from a folder on the IMAP server.

        :param folder_path: The name of the folder to unsubscribe from.
        :type folder_path: str
        :raises RequestException: If not connected to the server or if unsubscription fails.
        """
        logger_imap.debug("Unsubscribing from folder '%s'", folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)

            success, datas = self._exec_imap4_method(self.connection.unsubscribe, folder_path)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{folder_path}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                raise RequestException(f"Failed to unsubscribe to {folder_path}", err.ERROR_IMAP_FAILED)
            logger_imap.info("Successfully unsubscribe to folder '%s'", folder_path)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

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
        logger_imap.debug("Getting ACL for folder '%s'", folder_path)
        if self.connection is not None and self.authenticated:
            folder_path = self._fix_folder_path(folder_path)
            folder_path = quote(folder_path)
            success, datas = self._exec_imap4_method(self.connection.getacl, folder_path)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{folder_path}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                raise RequestException(f"Failed to unsubscribe to {folder_path}", err.ERROR_IMAP_FAILED)

            # Parse the response: data[0] is typically bytes like b'INBOX identifier1 rights1 identifier2 rights2 ...'
            response = datas[0].decode()

            # Split the response: first part is folder name, rest are identifier/rights pairs
            parts = response.split()

            # Skip first part (folder name) and parse pairs
            i = 1  # Start after folder name
            while i < len(parts) - 1:
                identifier = parts[i]
                imap_rights = parts[i + 1]
                # Convert IMAP rights string to SOGo rights dictionary
                sogo_rights = _convert_imap_to_rights(imap_rights)
                yield (identifier, sogo_rights)
                i += 2
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

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
        # Convert SOGo rights dictionary to IMAP rights string
        imap_rights = _convert_rights_to_imap(rights)

        logger_imap.debug("Setting ACL for folder '%s', identifier '%s', SOGo rights %s -> IMAP rights '%s'", folder_path, identifier, rights, imap_rights)
        if self.connection is not None and self.authenticated:
            folder_path = self._fix_folder_path(folder_path)
            folder_path = quote(folder_path)

            success, datas = self._exec_imap4_method(self.connection.setacl, folder_path, identifier, imap_rights)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{folder_path}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                raise RequestException(f"Failed to unsubscribe to {folder_path}", err.ERROR_IMAP_FAILED)

            logger_imap.info("Successfully set ACL for folder '%s', identifier '%s', IMAP rights '%s'",
                           folder_path, identifier, imap_rights)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def delete_acl(self, folder_path: str, identifier: str) -> None:
        """Delete ACL rights for a specific user/identifier on a folder.

        Uses the IMAP DELETEACL command to remove all permissions for an identifier.

        :param folder_path: The name of the folder.
        :type folder_path: str
        :param identifier: The user identifier to remove ACL for.
        :type identifier: str
        :raises RequestException: If not connected to the server or if deleting ACL fails.
        """
        logger_imap.debug("Deleting ACL for folder '%s', identifier '%s'", folder_path, identifier)
        if self.connection is not None and self.authenticated:
            folder_path = self._fix_folder_path(folder_path)
            folder_path = quote(folder_path)

            success, datas = self._exec_imap4_method(self.connection.deleteacl, folder_path, identifier)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{folder_path}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                raise RequestException(f"Failed to unsubscribe to {folder_path}", err.ERROR_IMAP_FAILED)
            logger_imap.info("Successfully deleted ACL for folder '%s', identifier '%s'", folder_path, identifier)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

#######
#MAILS#
#######

    def select_mailbox(self, mailbox: str, readonly: bool = False) -> int:
        """Select a mailbox

        In imap logic a mailbox must be selected before doing any action to it.

        There is a readonly mode where a mailbox cannot received modifying command.
        
        :param mailbox: The mailbox to select.
        :type mailbox: str
        :param readonly: The mailbox to select.
        :type mailbox: str
        :raises RequestException: If selecting the mailbox fails.
        :return: The number of messages in the selected mailbox.
        """
        logger_imap.debug("Selecting mailbox '%s'", mailbox)
        if self.connection is not None and self.authenticated:
            if not mailbox.isascii():
                raise RequestException(f"Mailbox name is not ascii: {mailbox}", err.ERROR_IMAP_NOT_ASCII)
            mailbox = quote(mailbox)
            success, datas = self._exec_imap4_method(self.connection.select, mailbox)
            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{mailbox}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                logger_imap.error("Cannot select folder %s: %s", mailbox, datas)
                raise RequestException(f"Failed to select folder {mailbox}", err.ERROR_IMAP_FAILED)
            nb_mails = int(datas[0])
            return nb_mails
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def uid_copy(self, mail_uid: str|list|Iterator, dest_mailbox: str) -> None:
        """
        Copy a mail form the selected folder to another folder

        :param mail_uid: uid of the mail
        :type mail_uid: int | str
        :param dest_mailbox: folder where to copy to
        :type dest_mailbox: str
        :raises RequestException: if dest_mailbox is not ascii
        :raises RequestException: if dest_mailbox does not exist
        :raises RequestException: if the copy failed
        :raises BugException: if manager not in a correct state (connected or authenticated)
        """
        logger_imap.debug("UID COPY '%s' to '%s'", mail_uid, dest_mailbox)
        if self.connection is not None and self.authenticated:
            if not dest_mailbox.isascii():
                raise RequestException(f"Mailbox name is not ascii: {dest_mailbox}", err.ERROR_IMAP_NOT_ASCII)
            if isinstance(mail_uid, (Iterator, list)):
                mail_uid = ','.join(mail_uid)
            dest_mailbox = quote(dest_mailbox)
            success, datas = self._exec_imap4_method(self.connection.uid, 'COPY', mail_uid, dest_mailbox)
            # Beware, if the uid does not exist, IMAP4 still return OK with data to None. Not a big problem, though.
            if not success:
                if datas[0].decode().startswith("[TRYCREATE]"):
                    raise RequestException(f"Folder '{dest_mailbox}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                logger_imap.error("UID COPY failed for UID %s to %s", mail_uid, dest_mailbox)
                raise RequestException(f"UID COPY failed for UID {mail_uid} to {dest_mailbox}", err.ERROR_IMAP_FAILED)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")


    def uid_store_flags(self, mail_uid: str|list|Iterator, flags: list[str], operation: str = '+FLAGS') -> int:
        """
        Do UID STORE (FLAGS) without selecting the mailbox (atomic).
        
        :param mail_uid: The UID of the mail to modify
        :type mail_uid: str|list|Iterator
        :param flags: list of flags to set/unset.
        :type flags: list[str]
        :param operation: The operation to perform ('+FLAGS', '-FLAGS', or 'FLAGS')., defaults to '+FLAGS'
        :type operation: str, optional
        :raises RequestException: If anything is wrong during the command
        :raises BugException: if manager not in a correct state (connected or authenticated)
        """
        logger_imap.debug("UID STORE %s '%s' flags %s", operation, mail_uid, flags)
        if self.connection is not None and self.authenticated:
            if isinstance(mail_uid, (Iterator, list)):
                mail_uid = ','.join(mail_uid)
            flags_str = '(' + ' '.join(flags) + ')'
            success, datas = self._exec_imap4_method(self.connection.uid, 'STORE', mail_uid, operation, flags_str)
            if not success:
                raise RequestException(f"UID STORE failed for UID {mail_uid} with flags {flags}: {datas}", err.ERROR_IMAP_FAILED)
            #datas is a list of bytes like this [b'1 (UID 7 FLAGS (\\Seen))', b'2 (UID 9 FLAGS (\\Seen))', ...]
            #showing all mails that has been modified, so len(datas) is the number of mail affected.
            return len(datas)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")


    def _parse_mail_fetching(self, message_parts: tuple[bytes, bytes]) -> dict:
        """
        Parse the answer of a fetch command, only works if the fetch was requesting
        (BODY.PEEK[] FLAGS UID). The dict returned has thoses info:

        ```    
        {
            "uid": uid, str
            "mail": mail object, Message
            "flags": flags_dict, dict
            "size": size, int
        }
        ```

        :param message_parts: (b'enevellope', b'data')
        :type message_parts: tuple[bytes, bytes]
        :return: _description_
        :rtype: dict
        """
        meta_bytes, mail_bytes = message_parts
        meta = meta_bytes.decode()
        try:
            # Parse UID
            uid_match = re.search(r'UID (\d+)', meta)
            uid = int(uid_match.group(1)) if uid_match else ""

            # Parse FLAGS
            flags_match = re.search(r'FLAGS \((.*?)\)', meta)
            flags_list = flags_match.group(1).split() if flags_match else []

            # Parse size from BODY[] {size} format in meta
            size_match = re.search(r'BODY\[?\]?\s*\{(\d+)\}', meta)
            size = int(size_match.group(1)) if size_match else len(mail_bytes)
        except IndexError as e:
            logger_imap.error("Can't parse the meta from mail: %s", meta)
            raise BugException(f"Can't parse the meta from mail: {meta}") from e

        # Structure flags
        flags_dict = {
            'seen': '\\Seen' in flags_list,
            'flagged': '\\Flagged' in flags_list,
            'answered': '\\Answered' in flags_list,
            'forwarded': '$Forwarded' in flags_list or '\\Forwarded' in flags_list,
            'all': flags_list
        }

        return {
            "uid": uid,
            "mail": message_from_bytes(mail_bytes),
            "flags": flags_dict,
            "size": size
        }

    def fetch_all_mails(self, folder_path: str, number_of_mails: int, offset: int) -> Iterator[dict]:
        """
        https://datatracker.ietf.org/doc/html/rfc9051#name-fetch-response
        Fetch a specific number of mails from a mailbox with full details.

        {
            "uid": uid, str
            "mail": mail object, Message
            "flags": flags_dict, dict
            "size": size, int
        }

        Always yield the totla number of mails of the folder
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
        logger_imap.debug("Fetching %d mails from '%s'", number_of_mails, folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            mailbox_len = self.select_mailbox(folder_path)

            #yield length
            yield {"nb_mails": mailbox_len}
            if mailbox_len == 0:
                return

            #Recent mail have the higest ID number, so we fetch from descending
            range_arg = f'{max(1, mailbox_len - number_of_mails + 1)}:{mailbox_len - offset}'
            # Fetch full message, flags, and UID (size is included in BODY.PEEK[] response)
            # If success, datas will be of length 2*nb_mails. Each mail is
            # a tuple (b'metadata', b'body') and  a singular b')'
            success, datas = self._exec_imap4_method(self.connection.fetch, range_arg, '(BODY.PEEK[] FLAGS UID)')

            if not success:
                if datas[0].decode().startswith("Error in IMAP command FETCH: Invalid messageset"):
                    #Goes here means our range args is wrong, it should'nt happen
                    raise BugException("Try to fetch mail with an unvalid messageset")
                raise RequestException(f"Fail to fetch mails: {datas}", err.ERROR_IMAP_FAILED)

            for part in reversed(datas):
                if not isinstance(part, tuple):
                    continue
                yield self._parse_mail_fetching(part)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def fetch_mails_by_uids(self, mailbox: str, uid_list: list[str]) -> list[dict[str, Any]]:
        """Fetch mails for a list of UIDs (atomique: select + single FETCH for list).

        :param mailbox: The mailbox to fetch mails from.
        :type mailbox: str
        :param uid_list: list of mail UIDs to fetch.
        :type uid_list: list[str]
        :raises RequestException: If fetching mails fails
        :return: A list of mail dicts
        :rtype: list[dict[str, Any]]
        """
        logger_imap.debug("Fetching mails by UIDs %s from '%s'", uid_list, mailbox)
        if self.connection is not None and self.authenticated:
            if not mailbox.isascii():
                raise RequestException(f"Mailbox name is not ascii: {mailbox}", err.ERROR_IMAP_NOT_ASCII)
            mailbox = quote(mailbox)
            mailbox_len = self.select_mailbox(mailbox)
            if mailbox_len == 0:
                return []

            uid_set = ",".join(uid_list)
            # Use BODY.PEEK[] instead of RFC822 to avoid marking as read, and ensure UID is included
            success, datas = self._exec_imap4_method(self.connection.uid, 'FETCH', uid_set, '(BODY.PEEK[] FLAGS UID)')

            if not success:
                if datas[0].decode().startswith("Error in IMAP command FETCH: Invalid messageset"):
                    #Goes here means our range args is wrong, it should'nt happen
                    raise BugException("Try to fetch mail with an unvalid messageset")
                raise RequestException(f"Fail to fetch mails: {datas}", err.ERROR_IMAP_FAILED)

            len_mail_fetch = int(len(datas)/2)
            mail_list: list = [None] * len_mail_fetch
            for part in datas:
                if not isinstance(part, tuple):
                    continue
                mail_list.append(self._parse_mail_fetching(part))
            return mail_list
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")


    def get_mail_uids_before_date(self, folder_path: str, before_date: str | None = None, exclude_deleted: bool = True) -> Iterator[str]:
        """Get all mail UIDs from a folder, optionally filtered before a date.

        :param folder_path: The name of the folder to search.
        :type folder_path: str
        :param before_date: The cutoff date (YYYY-MM-DD). Only mails before this date are returned.
        :type before_date: str | None
        :param exclude_deleted: Whether to exclude deleted emails from the search.
        :type exclude_deleted: bool
        :return: A list of mail UIDs as integers.
        :rtype: list[int]
        :raises RequestException: If the search fails.
        """
        logger_imap.debug("Fetching mail UIDs from '%s' before '%s'", folder_path, before_date)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            self.select_mailbox(folder_path)

            #build search criteria (date parsing isolated)
            criteria_parts: list[str] = []
            if exclude_deleted:
                criteria_parts.append("NOT DELETED")

            if before_date:
                # data in format 7-Mar-2026
                # https://datatracker.ietf.org/doc/html/rfc9051#name-formal-syntax
                try:
                    dt = datetime.strptime(before_date, "%Y-%m-%d")
                    formatted_date = dt.strftime("%d-%b-%Y")
                    criteria_parts.append(f"BEFORE {formatted_date}")
                except ValueError as exc:
                    raise RequestException(f"Invalid date format: {before_date}. Expected YYYY-MM-DD.") from exc

            criteria = "(" + " ".join(criteria_parts) + ")" if criteria_parts else "ALL"

            #perform search
            success, datas = self._exec_imap4_method(self.connection.uid, 'SEARCH', criteria)

            if not success:
                raise RequestException(f"Failed to search mails in {folder_path} with criteria {criteria}.")

            if datas:
                yield from parse_uids_from_bytes(datas[0])
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")


    def fetch_mail_raw(self, folder_path: str, mail_uid: str) -> str:
        """Fetch a mail from a specific mailbox using UID.

        :param mailbox: The mailbox containing the mail
        :type mailbox: str
        :param mail_uid: The UID of the mail to fetch (int)
        :type mail_uid: int
        :raises RequestException: If the operation fails
        :return: The raw bytes of the fetched mail
        :rtype: bytes
        """
        logger_imap.debug("Fetching mail UID '%s' from '%s'", mail_uid, folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            self.select_mailbox(folder_path)

            success, datas = self._exec_imap4_method(self.connection.uid, 'FETCH', mail_uid, '(RFC822)')
            if not success:
                raise RequestException(f"Failed to expunge mailbox {folder_path}", err.ERROR_IMAP_FAILED)
            if not datas or not isinstance(datas[0], tuple):
                raise RequestException(f"Mail UID {mail_uid} not found in {folder_path}.", err.ERROR_MAIL_UID_NOT_FOUND)
            #datas = [(b'UID X RFC822 {3723}', b'full_eml')]
            full_eml: bytes = datas[0][1]
            return full_eml.decode()
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def fetch_mail(self, folder_path: str, mail_uid: str) -> dict[str, Any]:
        """Fetch a mail with additional metadata (flags, size) from a specific mailbox using UID.

        ```    
        {
            "uid": uid, str
            "mail": mail object, Message
            "flags": flags_dict, dict
            "size": size, int
        }
        ```

        :param folder_path: The folder containing the mail
        :type folder_path: str
        :param mail_uid: The UID of the mail to fetch
        :type mail_uid: str
        :raises RequestException: If the operation fails
        :return: A dict containing raw_message (bytes), flags (dict), and size (int)
        :rtype: dict[str, Any]
        """
        logger_imap.debug("Fetching mail detail for UID '%s' from '%s'", mail_uid, folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            self.select_mailbox(folder_path)
            # Fetch full message and FLAGS (size is included in RFC822 response)
            success, datas = self._exec_imap4_method(self.connection.uid, 'FETCH', mail_uid, '(BODY.PEEK[] FLAGS UID)')
            if not success:
                raise RequestException(f"Failed to fetch mail {mail_uid} in folder {folder_path}", err.ERROR_IMAP_FAILED)
            if not datas or not isinstance(datas[0], tuple):
                raise RequestException(f"Mail UID {mail_uid} not found in {folder_path}.", err.ERROR_MAIL_UID_NOT_FOUND)

            return self._parse_mail_fetching(datas[0])
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def copy_mail_to_mailbox(self, folder_path: str, mail_uid: str, dest_folder_path: str) -> None:
        """Copy a mail from one mailbox to another using UID.
        Wrapper selecting folder_path then using uid_copy primitive.

        :param folder_path: The source folder_path.
        :type folder_path: str
        :param mail_uid: The UID of the mail to copy.
        :type mail_uid: int
        :param dest_folder_path: The destination folder_path.
        :type dest_folder_path: str
        :raises RequestException: If the operation fails.
        """
        logger_imap.debug("Copying mail UID '%s' from '%s' to '%s'", mail_uid, folder_path, dest_folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii() or not dest_folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path} and/or {dest_folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            dest_folder_path = quote(folder_path)
            self.uid_copy(mail_uid, dest_folder_path)
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

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
        logger_imap.debug("Adding flags %s to mail UID '%s' in '%s'", flags, mail_uid, folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            self.uid_store_flags(mail_uid, flags, operation='+FLAGS')
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def delete_mails_by_uid(self, folder_path: str, mail_uid: str|list[str]) -> None:
        """Delete a specific mail by UID (copy to Trash and mark as deleted).

        :param folder_path: The folder containing the mail.
        :type folder_path: str
        :param mail_uid: The UID or a list of uids of the mail to delete.
        :type mail_uid: str or list[str]
        :raises RequestException: If the operation fails.
        """
        logger_imap.debug("Deleting mail UID '%s' from mailbox '%s'", mail_uid, folder_path)
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)
            self.select_mailbox(folder_path)
            # Copy mail to Trash folder
            self.uid_copy(mail_uid, self.folders_map_type_to_name[cs.MAIL_FOLDER_TRASH])
            # Mark mail as deleted and seen
            self.uid_store_flags(mail_uid, ['\\Deleted'], operation='+FLAGS')
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def _get_folder_message_counts(self, folder_path: str) -> tuple[int, int]:
        """Get the total message count and unseen message count for a folder.

        :param folder_path: The name of the folder.
        :type folder_path: str
        :return: tuple of (message_count, unseen_count).
        :rtype: tuple[int, int]
        """
        if self.connection is not None and self.authenticated:
            if not folder_path.isascii():
                raise RequestException(f"Mailbox name is not ascii: {folder_path}", err.ERROR_IMAP_NOT_ASCII)
            folder_path = quote(folder_path)

            # Use STATUS command to get counts without selecting the mailbox
            # This is more efficient than SELECT for just getting counts
            success, datas = self._exec_imap4_method(self.connection.status, folder_path, '(MESSAGES UNSEEN)')

            if not success:
                if datas[0].decode().startswith("Mailbox doesn't exist"):
                    raise RequestException(f"Folder '{folder_path}' does not exist", err.ERROR_FOLDER_NAME_NOT_FOUND)
                raise RequestException(f"Failed to get status for  {folder_path}", err.ERROR_IMAP_FAILED)

            # Parse STATUS response: e.g., b'INBOX (MESSAGES 42 UNSEEN 5)'
            message_count = 0
            unseen_count = 0
            if datas:
                match = re.search(r"MESSAGES\s+(\d+).*?UNSEEN\s+(\d+)", datas[0].decode())
                if match:
                    message_count = int(match.group(1))
                    unseen_count = int(match.group(2))
            return message_count, unseen_count
        else:
            raise BugException("Not authenticated meaning self.connect() and self.login() was not called beforehands")

    def logout(self) -> None:
        """
        Log out from the IMAP server.

        Beware that after this state you will have to reinstantiate a connector

        :raises RequestException: If the operation fails.
        """
        logger_imap.info("Logging out from IMAP server")
        if self.connection is not None:
            self._exec_imap4_method(self.connection.logout)
            self.authenticated = False
            self.connected = False
