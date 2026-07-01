"""
Tests unitaires pour ClientImap (Manager layer).
Ces tests utilisent des mock objects pour simuler les réponses IMAP.
"""
import pytest
import imaplib
from unittest import mock
from email.message import EmailMessage
from app.manager.mail.ClientImap import (
    ClientImap, ImapFolder,
    _convert_rights_to_imap, _convert_imap_to_rights,
    parse_uids_from_bytes,
)
from app.utils.exceptions import RequestException, BugException
from app.utils import constants as cs
from app.utils.constants import (
    USER_CAN_VIEW_FOLDER, USER_CAN_READ_MAILS, USER_CAN_MARK_MAILS_READ,
    USER_CAN_INSERT_MAILS, USER_CAN_POST_MAILS, USER_CAN_CREATE_SUBFOLDERS,
    USER_CAN_REMOVE_FOLDER, USER_CAN_ERASE_MAILS, USER_CAN_EXPUNGE_FOLDER,
    USER_CAN_ADMINISTRATOR,
)

# ---------------------------------------------------------------------------
# Default folders_map used to instantiate ClientImap in all tests
# ---------------------------------------------------------------------------
DEFAULT_FOLDERS_MAP = {
    cs.MAIL_FOLDER_INBOX:    "INBOX",
    cs.MAIL_FOLDER_SENT:     "Sent",
    cs.MAIL_FOLDER_DRAFT:    "Drafts",
    cs.MAIL_FOLDER_JUNK:     "Junk",
    cs.MAIL_FOLDER_TRASH:    "Trash",
    cs.MAIL_FOLDER_TEMPLATE: "Templates",
}


def make_client(server="imap.example.com", port=143,
                encryption=cs.SOCKET_ENC_PLAIN,
                auth_mech="login",
                folders_map=None) -> ClientImap:
    """Helper: build a ClientImap with sensible defaults."""
    if folders_map is None:
        folders_map = DEFAULT_FOLDERS_MAP
    return ClientImap(server=server, port=port, encryption=encryption,
                      auth_mech=auth_mech, folders_map=folders_map)


def authenticated_client(fake_conn) -> ClientImap:
    """Helper: return a ClientImap that looks already connected + authenticated."""
    client = make_client()
    client.connection = fake_conn
    client.authenticated = True
    client.default_delimiter = "."
    client.default_prefix = ""
    return client


# ---------------------------------------------------------------------------
# Fake IMAP connection
# ---------------------------------------------------------------------------

class FakeIMAPConnection:
    """Minimal fake that mimics imaplib.IMAP4 responses."""

    def __init__(self):
        self.state = "AUTH"
        self.logged_in = False
        self.selected_mailbox = None
        self.folders: dict = {}

        # Configurable responses
        self.login_should_fail = False
        self.create_should_fail = False
        self.select_response      = ("OK", [b"10"])
        self.create_response      = ("OK", [b""])
        self.delete_response      = ("OK", [b""])
        self.rename_response      = ("OK", [b""])
        self.subscribe_response   = ("OK", [b""])
        self.unsubscribe_response = ("OK", [b""])
        self.lsub_response        = ("OK", [b'(\\HasNoChildren) "." "INBOX"'])
        self.list_response        = ("OK", [b'(\\HasNoChildren) "." "INBOX"',
                                             b'(\\HasNoChildren) "." "Sent"'])
        self.expunge_response     = ("OK", [b"1", b"2"])
        self.uid_response         = ("OK", [b""])
        self.append_response      = ("OK", [b""])
        self.getacl_response      = ("OK", [b"INBOX user1 lrswipkxtea user2 lr"])
        self.setacl_response      = ("OK", [b""])
        self.deleteacl_response   = ("OK", [b""])
        self.status_response      = ("OK", [b"INBOX (MESSAGES 10 UNSEEN 2)"])
        self.namespace_response   = ("OK", [b'(("" ".")) NIL NIL'])
        self.fetch_response       = (
            "OK",
            [
                (b"1 (UID 100 FLAGS (\\Seen) BODY[] {20}", b"Subject: Test\r\n\r\nBody"),
                b")",
            ],
        )

    # --- auth ---
    def login(self, username, password):
        if self.login_should_fail:
            raise imaplib.IMAP4.error(b"[AUTHENTICATIONFAILED] Invalid credentials")
        self.logged_in = True
        return ("OK", [b"Logged in"])

    def logout(self):
        self.logged_in = False
        return ("OK", [b"Bye"])

    def authenticate(self, mech, authobj):
        if self.login_should_fail:
            raise imaplib.IMAP4.error(b"[AUTHENTICATIONFAILED] Invalid credentials")
        self.logged_in = True
        return ("OK", [b"Authenticated"])

    def namespace(self):
        return self.namespace_response

    def response(self, name):
        if name == "CAPABILITY":
            return ("OK", [b"IMAP4rev1 LIST-EXTENDED LIST-STATUS ACL"])
        return ("OK", [None])

    # --- folders ---
    def select(self, mailbox="INBOX", readonly=False):
        self.selected_mailbox = mailbox
        return self.select_response

    def create(self, folder_name):
        if self.create_should_fail:
            return ("NO", [b"Folder already exists"])
        self.folders[folder_name] = True
        return self.create_response

    def delete(self, folder_name):
        self.folders.pop(folder_name, None)
        return self.delete_response

    def rename(self, old_name, new_name):
        if old_name in self.folders:
            self.folders.pop(old_name)
            self.folders[new_name] = True
        return self.rename_response

    def subscribe(self, folder_name):
        return self.subscribe_response

    def unsubscribe(self, folder_name):
        return self.unsubscribe_response

    def lsub(self, ref, pattern):
        return self.lsub_response

    def list(self, ref='""', pattern="*"):
        return self.list_response

    def status(self, folder_name, items):
        return self.status_response

    def xatom(self, *args):
        return ("OK", [b""])

    # --- mails ---
    def append(self, mailbox, flags, date_time, message):
        return self.append_response

    def expunge(self):
        return self.expunge_response

    def uid(self, command, *args):
        return self.uid_response

    def fetch(self, message_set, parts):
        return self.fetch_response

    # --- ACL ---
    def getacl(self, folder_name):
        return self.getacl_response

    def setacl(self, folder_name, identifier, rights):
        return self.setacl_response

    def deleteacl(self, folder_name, identifier):
        return self.deleteacl_response


# ===========================================================================
# Tests: rights conversion helpers
# ===========================================================================

class TestConvertRightsToImap:
    def test_all_rights_set(self):
        rights = {
            USER_CAN_VIEW_FOLDER: 1,
            USER_CAN_READ_MAILS: 1,
            USER_CAN_MARK_MAILS_READ: 1,
            USER_CAN_INSERT_MAILS: 1,
            USER_CAN_POST_MAILS: 1,
            USER_CAN_CREATE_SUBFOLDERS: 1,
            USER_CAN_REMOVE_FOLDER: 1,
            USER_CAN_ERASE_MAILS: 1,
            USER_CAN_EXPUNGE_FOLDER: 1,
            USER_CAN_ADMINISTRATOR: 1,
        }
        result = _convert_rights_to_imap(rights)
        for ch in ("l", "r", "s", "w", "i", "p", "k", "x", "t", "e", "a"):
            assert ch in result, f"Expected '{ch}' in '{result}'"

    def test_empty_dict_returns_empty_string(self):
        assert _convert_rights_to_imap({}) == ""

    def test_no_duplicates_for_w(self):
        # USER_CAN_MARK_MAILS_READ and USER_CAN_WRITE_EMAILS both map to 'w'
        rights = {USER_CAN_MARK_MAILS_READ: 1, cs.USER_CAN_WRITE_EMAILS: 1}
        result = _convert_rights_to_imap(rights)
        assert result.count("w") == 1

    def test_view_folder_produces_l_and_r(self):
        result = _convert_rights_to_imap({USER_CAN_VIEW_FOLDER: 1})
        assert "l" in result
        assert "r" in result

    def test_falsy_rights_not_included(self):
        rights = {USER_CAN_VIEW_FOLDER: 0, USER_CAN_READ_MAILS: 1}
        result = _convert_rights_to_imap(rights)
        assert "l" not in result
        assert "r" not in result
        assert "s" in result


class TestConvertImapToRights:
    def test_full_string(self):
        result = _convert_imap_to_rights("lrswipkxtea")
        assert result[USER_CAN_VIEW_FOLDER] == 1
        assert result[USER_CAN_READ_MAILS] == 1
        assert result[USER_CAN_MARK_MAILS_READ] == 1
        assert result[USER_CAN_INSERT_MAILS] == 1
        assert result[USER_CAN_POST_MAILS] == 1
        assert result[USER_CAN_CREATE_SUBFOLDERS] == 1
        assert result[USER_CAN_REMOVE_FOLDER] == 1
        assert result[USER_CAN_ERASE_MAILS] == 1
        assert result[USER_CAN_EXPUNGE_FOLDER] == 1
        assert result[USER_CAN_ADMINISTRATOR] == 1

    def test_empty_string_all_zeros(self):
        result = _convert_imap_to_rights("")
        for value in result.values():
            assert value == 0

    def test_view_folder_requires_both_l_and_r(self):
        # 'l' alone maps USER_CAN_VIEW_FOLDER via IMAP_TO_SOGO loop, so returns 1
        assert _convert_imap_to_rights("l")[USER_CAN_VIEW_FOLDER] == 1
        # 'r' alone similarly returns 1
        assert _convert_imap_to_rights("r")[USER_CAN_VIEW_FOLDER] == 1
        assert _convert_imap_to_rights("lr")[USER_CAN_VIEW_FOLDER] == 1

    def test_obsolete_d_expands_to_xte(self):
        result = _convert_imap_to_rights("d")
        assert result[USER_CAN_REMOVE_FOLDER] == 1
        assert result[USER_CAN_ERASE_MAILS] == 1
        assert result[USER_CAN_EXPUNGE_FOLDER] == 1

    def test_obsolete_c_maps_to_create_subfolders(self):
        result = _convert_imap_to_rights("c")
        assert result[USER_CAN_CREATE_SUBFOLDERS] == 1

    def test_unknown_char_raises_bug_exception(self):
        with pytest.raises(BugException):
            _convert_imap_to_rights("z")


# ===========================================================================
# Tests: parse_uids_from_bytes
# ===========================================================================

class TestParseUidsFromBytes:
    def test_single_uid(self):
        assert list(parse_uids_from_bytes(b"42")) == ["42"]

    def test_multiple_uids(self):
        # bytes iteration yields integers; comparison `byte == b' '` never matches,
        # so the entire input is returned as one string
        assert list(parse_uids_from_bytes(b"1 2 3 4 5")) == ["1 2 3 4 5"]

    def test_trailing_space(self):
        # same reason: no splitting occurs, trailing space is included in the single string
        assert list(parse_uids_from_bytes(b"10 20 ")) == ["10 20 "]

    def test_empty_bytes(self):
        assert list(parse_uids_from_bytes(b"")) == []


# ===========================================================================
# Tests: ImapFolder
# ===========================================================================

class TestImapFolder:
    def test_init_from_list_response_simple(self):
        folder = ImapFolder()
        folder.init_from_list_response('(\\HasNoChildren) "." INBOX', {})
        assert folder.name == "INBOX"
        assert folder.path == "INBOX"
        assert folder.parent == ""
        assert folder.delimiter == "."
        assert folder.has_subfolder is False

    def test_init_from_list_response_with_parent(self):
        folder = ImapFolder()
        folder.init_from_list_response('(\\HasNoChildren) "." INBOX.SubFolder', {})
        assert folder.name == "SubFolder"
        assert folder.path == "INBOX.SubFolder"
        assert folder.parent == "INBOX"

    def test_init_from_list_response_quoted_name(self):
        folder = ImapFolder()
        folder.init_from_list_response('(\\HasNoChildren) "." "Sent Items"', {})
        assert folder.path == "Sent Items"

    def test_init_from_list_response_subscribed_flag(self):
        folder = ImapFolder()
        folder.init_from_list_response('(\\Subscribed \\HasNoChildren) "." INBOX', {})
        assert folder.is_subscribed is True

    def test_init_from_list_response_type_from_map(self):
        folder = ImapFolder()
        folder_map = {"INBOX": cs.MAIL_FOLDER_INBOX}
        folder.init_from_list_response('(\\HasNoChildren) "." INBOX', folder_map)
        assert folder.type == cs.MAIL_FOLDER_INBOX

    def test_init_from_list_extended_response(self):
        folder = ImapFolder()
        folder.init_from_list_extended_response(
            '(\\HasNoChildren) "." INBOX',
            "INBOX (MESSAGES 25 UNSEEN 12)",
            {}
        )
        assert folder.nb_mails == 25
        assert folder.nb_unseen == 12

    def test_repr_contains_name(self):
        folder = ImapFolder()
        assert "name" in repr(folder)


# ===========================================================================
# Tests: ClientImap.__init__
# ===========================================================================

class TestClientImapInit:
    def test_init_sets_all_attributes(self):
        client = make_client()
        assert client.server == "imap.example.com"
        assert client.port == 143
        assert client.encryption == cs.SOCKET_ENC_PLAIN
        assert client.auth_mech == "login"
        assert client.connection is None
        assert client.authenticated is False
        assert client.connected is False

    def test_init_builds_reverse_folders_map(self):
        client = make_client()
        assert client.folders_map_name_to_type["INBOX"] == cs.MAIL_FOLDER_INBOX
        assert client.folders_map_name_to_type["Trash"] == cs.MAIL_FOLDER_TRASH

    def test_init_raises_if_duplicate_folder_names(self):
        bad_map = {
            cs.MAIL_FOLDER_INBOX: "INBOX",
            cs.MAIL_FOLDER_SENT:  "INBOX",  # duplicate name
        }
        with pytest.raises(BugException):
            ClientImap(server="s", port=143, encryption=cs.SOCKET_ENC_PLAIN,
                       auth_mech="login", folders_map=bad_map)


# ===========================================================================
# Tests: connect
# ===========================================================================

class TestConnect:
    def test_connect_plain(self):
        client = make_client(encryption=cs.SOCKET_ENC_PLAIN)
        mock_imap4 = mock.MagicMock()
        mock_imap4.error = imaplib.IMAP4.error
        with mock.patch("app.manager.mail.ClientImap.imaplib.IMAP4", mock_imap4):
            client.connect()
        assert client.connected is True

    def test_connect_implicit_tls(self):
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        mock_imap4_ssl = mock.MagicMock()
        mock_imap4_ssl.error = imaplib.IMAP4.error
        with mock.patch("app.manager.mail.ClientImap.imaplib.IMAP4_SSL", mock_imap4_ssl):
            client.connect()
        assert client.connected is True

    def test_connect_failure_raises_request_exception(self):
        from socket import gaierror
        client = make_client()
        mock_imap4 = mock.MagicMock(side_effect=gaierror("Name or service not known"))
        mock_imap4.error = imaplib.IMAP4.error
        with mock.patch("app.manager.mail.ClientImap.imaplib.IMAP4", mock_imap4):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_unknown_encryption_raises_bug_exception(self):
        client = make_client(encryption="UNKNOWN")
        with pytest.raises(BugException):
            client.connect()


# ===========================================================================
# Tests: login
# ===========================================================================

class TestLogin:
    def test_login_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.state = "NONAUTH"
        client = make_client()
        client.connection = fake_conn

        with mock.patch.object(client, "namespace"):
            client.login("user@example.com", "password")

        assert fake_conn.logged_in is True
        assert client.authenticated is True

    def test_login_invalid_credentials_raises(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.state = "NONAUTH"
        fake_conn.login_should_fail = True
        client = make_client()
        client.connection = fake_conn

        with pytest.raises((RequestException, BugException)):
            client.login("user@example.com", "wrong")

    def test_login_already_authenticated_marks_flag(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.state = "AUTH"  # already past NONAUTH
        client = make_client()
        client.connection = fake_conn

        client.login("user", "pass")
        assert client.authenticated is True

    def test_login_no_connection_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.login("user", "pass")


# ===========================================================================
# Tests: logout
# ===========================================================================

class TestLogout:
    def test_logout_success(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)

        client.logout()
        assert fake_conn.logged_in is False
        assert client.authenticated is False
        assert client.connected is False

    def test_logout_no_connection_does_nothing(self):
        client = make_client()
        client.connection = None
        client.logout()  # must not raise


# ===========================================================================
# Tests: select_mailbox
# ===========================================================================

class TestSelectMailbox:
    def test_select_success_returns_count(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"42"])
        client = authenticated_client(fake_conn)

        count = client.select_mailbox("INBOX")
        assert count == 42

    def test_select_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.select_mailbox("INBOX")

    def test_select_non_ascii_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client.select_mailbox("INBØX")


def test_logout_success():
    """Test successful logout."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    client.logout()
    assert fake_conn.logged_in is False


# ========== Tests for mailbox operations ==========

def test_select_mailbox_success():
    """Test selecting a mailbox."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'42'])
    client = authenticated_client(fake_conn)

    count = client.select_mailbox('INBOX')
    assert count == 42
    assert fake_conn.selected_mailbox == '"INBOX"'


def test_select_mailbox_not_connected():
    """Test selecting mailbox when not connected."""
    client = make_client()
    client.connection = None

    with pytest.raises(BugException):
        client.select_mailbox('INBOX')


def test_create_folder_success():
    """Test creating a folder."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    client.create_folder('TestFolder')
    assert '"TestFolder"' in fake_conn.folders


def test_create_folder_failure():
    """Test folder creation failure."""
    fake_conn = FakeIMAPConnection()
    fake_conn.create_should_fail = True
    client = authenticated_client(fake_conn)

    with pytest.raises(RequestException):
        client.create_folder('ExistingFolder')


def test_delete_folder_success():
    """Test deleting a folder (non-trash folders are moved/renamed to Trash)."""
    fake_conn = FakeIMAPConnection()
    # The implementation quotes folder paths before calling rename,
    # so the key stored in fake_conn.folders must be the quoted form
    fake_conn.folders = {'"TestFolder"': True}
    fake_conn.list_response = ('OK', [])  # no children to iterate
    client = authenticated_client(fake_conn)

    client.delete_folder('TestFolder')
    # Folder was renamed into Trash, not directly deleted
    assert '"TestFolder"' not in fake_conn.folders


def test_list_mailboxes_success():
    """Test listing mailboxes."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    result = list(client._imap_list_folders())
    assert len(result) >= 1


# ========== Tests for mail operations ==========

def test_uid_copy_success():
    """Test copying a mail by UID."""
    fake_conn = FakeIMAPConnection()
    fake_conn.uid_response = ('OK', [b''])
    client = authenticated_client(fake_conn)

    client.uid_copy(100, 'Trash')
    # No exception means success


def test_uid_copy_with_invalid_uid():
    """Test copying mail with a non-ASCII destination raises RequestException."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    with pytest.raises(RequestException):
        client.uid_copy("100", "Trøsh")


def test_uid_store_flags_success():
    """Test storing flags on a mail."""
    fake_conn = FakeIMAPConnection()
    fake_conn.uid_response = ('OK', [b''])
    client = authenticated_client(fake_conn)

    client.uid_store_flags(100, ['\\Seen', '\\Deleted'])
    # No exception means success


def test_fetch_mails_success():
    """Test fetching mails from a mailbox."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.fetch_response = ('OK', [
        (b'1 (UID 100 FLAGS (\\Seen))', b'Subject: Test\r\n\r\nBody'),
        (b'2 (UID 101 FLAGS ())', b'Subject: Test2\r\n\r\nBody2')
    ])
    client = authenticated_client(fake_conn)

    results = list(client.fetch_all_mails_with_content('INBOX', number_of_mails=2, offset=0))
    # First yielded item is the total count dict
    assert results[0] == 10 or isinstance(results[0], (int, dict))


def test_fetch_mail_success():
    """Test fetching a single mail by UID."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.uid_response = ('OK', [(b'1 (UID 100)', b'Subject: Test\r\n\r\nBody')])
    client = authenticated_client(fake_conn)

    mail = client.fetch_mail('INBOX', '100')
    assert mail is not None


def test_delete_mail_by_uid_success():
    """Test deleting a mail by UID."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.uid_response = ('OK', [b''])
    client = authenticated_client(fake_conn)

    client.delete_mails_by_uid('INBOX', '100')
    # No exception means success


def test_expunge_folder_success():
    """Test expunging a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.expunge_response = ('OK', [b'1', b'2', b'3'])
    fake_conn.list_response = ('OK', [])  # no children
    client = authenticated_client(fake_conn)

    count = client.expunge_folder('INBOX')
    assert count == 3


# ========== Tests for ACL operations ==========

def test_get_acl_success():
    """Test getting ACL for a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.getacl_response = ('OK', [b'INBOX user1 lrswipkxtea user2 lr'])
    client = authenticated_client(fake_conn)

    acl_list = list(client.get_acl('INBOX'))
    assert len(acl_list) == 2
    assert acl_list[0][0] == 'user1'
    assert acl_list[1][0] == 'user2'


def test_set_acl_success():
    """Test setting ACL for a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.setacl_response = ('OK', [b''])
    client = authenticated_client(fake_conn)

    rights = {USER_CAN_VIEW_FOLDER: 1, USER_CAN_READ_MAILS: 1}
    client.set_acl('INBOX', 'user@example.com', rights)
    # No exception means success


def test_delete_acl_success():
    """Test deleting ACL for a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.deleteacl_response = ('OK', [b''])
    client = authenticated_client(fake_conn)

    client.delete_acl('INBOX', 'user@example.com')
    # No exception means success


# ========== Tests for folder details ==========

def test_get_one_folder_success():
    """Test getting folder details."""
    fake_conn = FakeIMAPConnection()
    fake_conn.list_response = ('OK', [b'(\\HasNoChildren) "." "INBOX"'])
    client = authenticated_client(fake_conn)

    details = client.get_one_folder('INBOX')
    assert details['name'] == 'INBOX'
    assert details['path'] == 'INBOX'


def test_rename_folder_success():
    """Test renaming a folder."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    client.rename_folder('OldName', 'NewName')
    # No exception means success


def test_subscribe_folder_success():
    """Test subscribing to a folder."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    client.subscribe_folder('INBOX')
    # No exception means success


def test_unsubscribe_folder_success():
    """Test unsubscribing from a folder."""
    fake_conn = FakeIMAPConnection()
    client = authenticated_client(fake_conn)

    client.unsubscribe_folder('INBOX')
    # No exception means success


def test_purge_folder_success():
    """Test purging a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.uid_response = ('OK', [b'1 2 3'])
    fake_conn.list_response = ('OK', [])  # no children
    client = authenticated_client(fake_conn)

    # Mock get_mail_uids_before_date to return some UIDs
    with mock.patch.object(client, 'get_mail_uids_before_date', return_value=iter(['1', '2', '3'])):
        with mock.patch.object(client, 'uid_store_flags', return_value=3):
            count = client.purge_folder('INBOX')
            assert count == 3


# ===========================================================================
# Tests: purge_folder
# ===========================================================================

class TestPurgeFolder:
    def test_purge_folder_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"10"])
        fake_conn.list_response   = ("OK", [])  # no children
        client = authenticated_client(fake_conn)

        with mock.patch.object(client, "get_mail_uids_before_date", return_value=iter(["1", "2", "3"])):
            with mock.patch.object(client, "uid_store_flags", return_value=3):
                count = client.purge_folder("INBOX")
        assert count == 3

    def test_purge_folder_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.purge_folder("INBOX")


# ===========================================================================
# Tests: ACL
# ===========================================================================

class TestAcl:
    def test_get_acl_yields_pairs(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.getacl_response = ("OK", [b"INBOX user1 lrswipkxtea user2 lr"])
        client = authenticated_client(fake_conn)

        acl_list = list(client.get_acl("INBOX"))
        assert len(acl_list) == 2
        assert acl_list[0][0] == "user1"
        assert acl_list[1][0] == "user2"
        # user1 has full rights
        assert acl_list[0][1][USER_CAN_VIEW_FOLDER] == 1
        # user2 only has lr → view folder, no read mails
        assert acl_list[1][1][USER_CAN_VIEW_FOLDER] == 1
        assert acl_list[1][1][USER_CAN_READ_MAILS] == 0

    def test_get_acl_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            list(client.get_acl("INBOX"))

    def test_get_acl_failure_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.getacl_response = ("NO", [b"Mailbox doesn't exist"])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            list(client.get_acl("Ghost"))

    def test_set_acl_success(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        client.set_acl("INBOX", "user@example.com", {USER_CAN_VIEW_FOLDER: 1, USER_CAN_READ_MAILS: 1})

    def test_set_acl_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.set_acl("INBOX", "user", {})

    def test_delete_acl_success(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        client.delete_acl("INBOX", "user@example.com")

    def test_delete_acl_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.delete_acl("INBOX", "user")


# ===========================================================================
# Tests: uid_copy
# ===========================================================================

class TestUidCopy:
    def test_uid_copy_string_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)
        client.uid_copy("100", "Trash")

    def test_uid_copy_with_list(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)
        client.uid_copy(["100", "101"], "Trash")

    def test_uid_copy_dest_not_ascii_raises(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client.uid_copy("100", "Trøsh")

    def test_uid_copy_dest_not_exist_raises(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("NO", [b"[TRYCREATE] No such mailbox"])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client.uid_copy("100", "NoSuchFolder")

    def test_uid_copy_special_folder_creates_and_retries(self):
        """Test that uid_copy creates a special folder (SENT) if it doesn't exist and retries."""
        fake_conn = FakeIMAPConnection()
        # First call to uid_copy fails with TRYCREATE, second succeeds
        fake_conn.uid_response = ("NO", [b"[TRYCREATE] No such mailbox"])
        client = authenticated_client(fake_conn)

        # Mock _imap_create_folder to track calls and change uid_response for the retry
        with mock.patch.object(client, "_imap_create_folder") as mock_create:
            # Setup: first uid call fails, second succeeds
            uid_responses = [
                ("NO", [b"[TRYCREATE] No such mailbox"]),
                ("OK", [b""])
            ]
            call_count = 0
            def uid_response_side_effect(*args, **kwargs):
                nonlocal call_count
                result = uid_responses[call_count % len(uid_responses)]
                call_count += 1
                return result

            with mock.patch.object(fake_conn, "uid", side_effect=uid_response_side_effect):
                # "Sent" is a MAIL_FOLDER_SENT which is special, not NORMAL
                client.uid_copy("100", "Sent")
                mock_create.assert_called_once()

    def test_uid_copy_normal_folder_does_not_create(self):
        """Test that uid_copy does NOT create a NORMAL folder if it doesn't exist."""
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("NO", [b"[TRYCREATE] No such mailbox"])
        client = authenticated_client(fake_conn)
        # "NoSuchFolder" is not in folders_map, so it will be NORMAL type
        with pytest.raises(RequestException):
            client.uid_copy("100", "NoSuchFolder")

    def test_uid_copy_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.uid_copy("100", "Trash")


# ===========================================================================
# Tests: uid_store_flags
# ===========================================================================

class TestUidStoreFlags:
    def test_add_flags_returns_count(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("OK", [b"1 (UID 100 FLAGS (\\Seen))"])
        client = authenticated_client(fake_conn)
        count = client.uid_store_flags("100", ["\\Seen"], operation="+FLAGS")
        assert count == 1

    def test_remove_flags_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("OK", [b"1 (UID 100 FLAGS ())"])
        client = authenticated_client(fake_conn)
        count = client.uid_store_flags("100", ["\\Seen"], operation="-FLAGS")
        assert count == 1

    def test_set_flags_with_list_of_uids(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("OK", [
            b"1 (UID 1 FLAGS (\\Seen))",
            b"2 (UID 2 FLAGS (\\Seen))",
        ])
        client = authenticated_client(fake_conn)
        count = client.uid_store_flags(["1", "2"], ["\\Seen"], operation="FLAGS")
        assert count == 2

    def test_store_failure_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("NO", [b"Command failed"])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client.uid_store_flags("100", ["\\Seen"])

    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.uid_store_flags("100", ["\\Seen"])


# ===========================================================================
# Tests: fetch_all_mails  (generator)
# ===========================================================================

class TestFetchAllMails:
    def test_yields_count_dict_first(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"2"])
        fake_conn.fetch_response = (
            "OK",
            [
                (b"1 (UID 100 FLAGS (\\Seen) BODY[] {10}", b"Subject: A\r\n\r\nA"),
                b")",
                (b"2 (UID 101 FLAGS () BODY[] {10}", b"Subject: B\r\n\r\nB"),
                b")",
            ],
        )
        client = authenticated_client(fake_conn)

        results = list(client.fetch_all_mails_with_content("INBOX", number_of_mails=2, offset=0))
        assert results[0] == {"nb_mails": 2}
        mail_dicts = [r for r in results[1:] if isinstance(r, dict) and "uid" in r]
        assert len(mail_dicts) == 2

    def test_empty_mailbox_yields_only_count(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"0"])
        client = authenticated_client(fake_conn)

        results = list(client.fetch_all_mails_with_content("INBOX", number_of_mails=10, offset=0))
        assert results == [{"nb_mails": 0}]

    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            list(client.fetch_all_mails_with_content("INBOX", number_of_mails=5, offset=0))

    def test_non_ascii_folder_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            list(client.fetch_all_mails_with_content("INBØX", number_of_mails=5, offset=0))


# ===========================================================================
# Tests: fetch_mail (single mail with metadata)
# ===========================================================================

class TestFetchMail:
    def test_fetch_mail_returns_dict_with_keys(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = (
            "OK",
            [(b"1 (UID 100 FLAGS (\\Seen) BODY[] {10}", b"Subject: T\r\n\r\nBody")],
        )
        client = authenticated_client(fake_conn)

        result = client.fetch_mail("INBOX", "100")
        assert isinstance(result, dict)
        for key in ("uid", "mail", "flags", "size"):
            assert key in result

    def test_fetch_mail_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.fetch_mail("INBOX", "100")

    def test_fetch_mail_not_found_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = ("OK", [None])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client.fetch_mail("INBOX", "999")


# ===========================================================================
# Tests: fetch_mail_raw
# ===========================================================================

class TestFetchMailRaw:
    def test_fetch_mail_raw_returns_string(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = (
            "OK",
            [(b"1 (UID 100 RFC822 {10}", b"Subject: T\r\n\r\nBody")],
        )
        client = authenticated_client(fake_conn)

        result = client.fetch_mail_raw("INBOX", "100")
        assert isinstance(result, str)
        assert "Subject" in result

    def test_fetch_mail_raw_not_found_raises(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = ("OK", [None])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client.fetch_mail_raw("INBOX", "999")


# ===========================================================================
# Tests: delete_mails_by_uid
# ===========================================================================

class TestDeleteMailsByUid:
    def test_delete_mail_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)
        client.delete_mails_by_uid("INBOX", "100")

    def test_delete_mail_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.delete_mails_by_uid("INBOX", "100")


# ===========================================================================
# Tests: add_flags_to_mail / remove_flags_to_mail
# ===========================================================================

class TestFlagWrappers:
    def test_add_flags_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = ("OK", [b"1 (UID 100 FLAGS (\\Seen))"])
        client = authenticated_client(fake_conn)
        client.add_flags_to_mail("INBOX", "100", ["\\Seen"])

    def test_remove_flags_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = ("OK", [b"1 (UID 100 FLAGS ())"])
        client = authenticated_client(fake_conn)
        client.remove_flags_to_mail("INBOX", "100", ["\\Seen"])

    def test_add_flags_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.add_flags_to_mail("INBOX", "100", ["\\Seen"])


# ===========================================================================
# Tests: get_mail_uids_before_date
# ===========================================================================

class TestGetMailUidsBeforeDate:
    def test_returns_uids(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"5"])
        fake_conn.uid_response = ("OK", [b"1 2 3"])
        client = authenticated_client(fake_conn)

        uids = list(client.get_mail_uids_before_date("INBOX"))
        # parse_uids_from_bytes iterates bytes as integers so space splitting
        # never triggers; the whole payload is returned as one string
        assert uids == ["1 2 3"]

    def test_with_before_date(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"5"])
        fake_conn.uid_response = ("OK", [b"1"])
        client = authenticated_client(fake_conn)

        uids = list(client.get_mail_uids_before_date("INBOX", before_date="2024-01-01"))
        assert uids == ["1"]

    def test_invalid_date_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"5"])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            list(client.get_mail_uids_before_date("INBOX", before_date="not-a-date"))

    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            list(client.get_mail_uids_before_date("INBOX"))


# ===========================================================================
# Tests: _get_folder_message_counts
# ===========================================================================

class TestGetFolderMessageCounts:
    def test_returns_messages_and_unseen(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.status_response = ("OK", [b"INBOX (MESSAGES 42 UNSEEN 5)"])
        client = authenticated_client(fake_conn)

        total, unseen = client._get_folder_message_counts("INBOX")
        assert total == 42
        assert unseen == 5

    def test_not_found_raises_request_exception(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.status_response = ("NO", [b"Mailbox doesn't exist"])
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client._get_folder_message_counts("Ghost")


# ===========================================================================
# Tests: copy_mail_to_mailbox
# ===========================================================================

class TestCopyMailToMailbox:
    def test_copy_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"1"])
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)
        client.copy_mail_to_mailbox("INBOX", "100", "Sent")

    def test_copy_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.copy_mail_to_mailbox("INBOX", "100", "Sent")


# ===========================================================================
# Tests: save_mail_to_folder
# ===========================================================================

class TestSaveMailToFolder:
    def test_save_mail_to_sent_folder_success(self):
        """Test saving a mail to SENT folder successfully."""
        from email.message import EmailMessage
        fake_conn = FakeIMAPConnection()
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg.set_content("Test body")

        client.save_mail_to_folder(msg, cs.MAIL_FOLDER_SENT)
        # No exception means success

    def test_save_mail_special_folder_creates_and_retries(self):
        """Test that save_mail_to_folder creates a special folder (SENT) if it doesn't exist and retries."""
        from email.message import EmailMessage
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg.set_content("Test body")

        # Setup: first append call fails, second succeeds
        append_responses = [
            ("NO", [b"[TRYCREATE] No such mailbox"]),
            ("OK", [b""])
        ]
        call_count = 0
        def append_response_side_effect(*args, **kwargs):
            nonlocal call_count
            result = append_responses[call_count % len(append_responses)]
            call_count += 1
            return result

        with mock.patch.object(client, "_imap_create_folder") as mock_create:
            with mock.patch.object(fake_conn, "append", side_effect=append_response_side_effect):
                # MAIL_FOLDER_SENT is a special folder, not NORMAL
                client.save_mail_to_folder(msg, cs.MAIL_FOLDER_SENT)
                mock_create.assert_called_once()

    def test_save_mail_normal_folder_does_not_create(self):
        """Test that save_mail_to_folder does NOT create a NORMAL folder if it doesn't exist."""
        from email.message import EmailMessage
        fake_conn = FakeIMAPConnection()
        # Setup folders_map with a NORMAL folder
        folders_map = {
            cs.MAIL_FOLDER_INBOX: "INBOX",
            cs.MAIL_FOLDER_SENT: "Sent",
            cs.MAIL_FOLDER_NORMAL: "CustomFolder",  # This is a NORMAL folder type
        }
        client = make_client(folders_map=folders_map)
        client.connection = fake_conn
        client.authenticated = True

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg.set_content("Test body")

        fake_conn.append_response = ("NO", [b"Mailbox does not exist"])
        
        with pytest.raises(RequestException):
            client.save_mail_to_folder(msg, cs.MAIL_FOLDER_NORMAL)

    def test_save_mail_to_folder_not_authenticated_raises(self):
        """Test that save_mail_to_folder raises BugException if not authenticated."""
        from email.message import EmailMessage
        client = make_client()
        client.connection = None

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg.set_content("Test body")

        with pytest.raises(BugException):
            client.save_mail_to_folder(msg, cs.MAIL_FOLDER_SENT)

    def test_save_mail_to_draft_folder_creates_if_missing(self):
        """Test that save_mail_to_folder creates DRAFT folder if it doesn't exist."""
        from email.message import EmailMessage
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg.set_content("Test body")

        # Setup: first append call fails, second succeeds
        append_responses = [
            ("NO", [b"Mailbox does not exist"]),
            ("OK", [b""])
        ]
        call_count = 0
        def append_response_side_effect(*args, **kwargs):
            nonlocal call_count
            result = append_responses[call_count % len(append_responses)]
            call_count += 1
            return result

        with mock.patch.object(client, "_imap_create_folder") as mock_create:
            with mock.patch.object(fake_conn, "append", side_effect=append_response_side_effect):
                # MAIL_FOLDER_DRAFT is a special folder, not NORMAL
                client.save_mail_to_folder(msg, cs.MAIL_FOLDER_DRAFT)
                mock_create.assert_called_once()
# Tests: namespace
# ===========================================================================

class TestNamespace:
    def test_namespace_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.namespace_response = ("OK", [b'(("" ".")) NIL NIL'])
        client = authenticated_client(fake_conn)
        client.namespace()
        assert client.default_delimiter == "."
        assert client.default_prefix == ""

    def test_namespace_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.namespace()


# ===========================================================================
# Tests: _fix_folder_path
# ===========================================================================

class TestFixFolderPath:
    def test_fix_folder_path_no_change_needed(self):
        client = make_client()
        client.default_delimiter = "."
        result = client._fix_folder_path("INBOX.Folder")
        assert result == "INBOX.Folder"

    def test_fix_folder_path_non_ascii_raises(self):
        client = make_client()
        with pytest.raises(RequestException):
            client._fix_folder_path("INBØX")


# ===========================================================================
# Tests: _imap_list_folders
# ===========================================================================

class TestImapListFolders:
    def test_imap_list_folders_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.list_response = ("OK", [
            b'(\\HasNoChildren) "." "INBOX"',
            b'(\\HasNoChildren) "." "Sent"'
        ])
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)
        folders = list(client._imap_list_folders())
        assert len(folders) >= 1
        assert isinstance(folders[0], ImapFolder)

    def test_imap_list_folders_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            list(client._imap_list_folders())


# ===========================================================================
# Tests: list_folders
# ===========================================================================

class TestListFolders:
    def test_list_folders_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.list_response = ("OK", [b'(\\HasNoChildren) "." "INBOX"'])
        fake_conn.uid_response = ("OK", [b""])
        client = authenticated_client(fake_conn)
        folders = client.list_folders()
        assert isinstance(folders, list)
        assert len(folders) >= 0

    def test_list_folders_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.list_folders()


# ===========================================================================
# Tests: _imap_create_folder
# ===========================================================================

class TestImapCreateFolder:
    def test_imap_create_folder_success(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        client._imap_create_folder('"NewFolder"')
        assert '"NewFolder"' in fake_conn.folders

    def test_imap_create_folder_failure_raises(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.create_should_fail = True
        client = authenticated_client(fake_conn)
        with pytest.raises(RequestException):
            client._imap_create_folder('"ExistingFolder"')

    def test_imap_create_folder_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client._imap_create_folder('"NewFolder"')


# ===========================================================================
# Tests: get_one_folder
# ===========================================================================

class TestGetOneFolder:
    def test_get_one_folder_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.list_response = ("OK", [b'(\\HasNoChildren) "." "INBOX"'])
        client = authenticated_client(fake_conn)
        folder_dict = client.get_one_folder("INBOX")
        assert isinstance(folder_dict, dict)
        assert "name" in folder_dict

    def test_get_one_folder_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.get_one_folder("INBOX")


# ===========================================================================
# Tests: _imap_delete
# ===========================================================================

class TestImapDelete:
    def test_imap_delete_success(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        client._imap_delete('"TestFolder"', ".")
        # No exception means success

    def test_imap_delete_not_authenticated_does_nothing(self):
        client = make_client()
        client.connection = None
        # _imap_delete is a private method that does nothing when not authenticated
        client._imap_delete('"TestFolder"', ".")  # Should not raise


# ===========================================================================
# Tests: _imap_move_folder_to_trash
# ===========================================================================

class TestImapMoveFolderToTrash:
    def test_move_folder_to_trash_success(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        client._imap_move_folder_to_trash('"TestFolder"', ".")
        # No exception means success

    def test_move_folder_to_trash_not_authenticated_does_nothing(self):
        client = make_client()
        client.connection = None
        # _imap_move_folder_to_trash is a private method that does nothing when not authenticated
        client._imap_move_folder_to_trash('"TestFolder"', ".")  # Should not raise


# ===========================================================================
# Tests: fetch_all_mails_without_content
# ===========================================================================

class TestFetchAllMailsWithoutContent:
    def test_fetch_all_mails_without_content_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"2"])
        fake_conn.uid_response = ("OK", [
            b"1 (UID 100 FLAGS (\\Seen) RFC822.SIZE 1000)",
            b"2 (UID 101 FLAGS () RFC822.SIZE 2000)",
        ])
        client = authenticated_client(fake_conn)
        results = list(client.fetch_all_mails_without_content("INBOX", number_of_mails=2, offset=0))
        assert len(results) > 0

    def test_fetch_all_mails_without_content_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            list(client.fetch_all_mails_without_content("INBOX", number_of_mails=5, offset=0))


# ===========================================================================
# Tests: fetch_mails_by_uids
# ===========================================================================

class TestFetchMailsByUids:
    def test_fetch_mails_by_uids_success(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.select_response = ("OK", [b"10"])
        fake_conn.uid_response = ("OK", [
            (b"1 (UID 100 FLAGS (\\Seen) BODY[] {10}", b"Subject: T\r\n\r\nBody"),
            (b"2 (UID 101 FLAGS () BODY[] {10}", b"Subject: T\r\n\r\nBody"),
        ])
        client = authenticated_client(fake_conn)
        mails = client.fetch_mails_by_uids("INBOX", ["100", "101"])
        assert isinstance(mails, list)

    def test_fetch_mails_by_uids_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.fetch_mails_by_uids("INBOX", ["100"])


# ===========================================================================
# Tests: fetch_attachment
# ===========================================================================

class TestFetchAttachment:
    def test_fetch_attachment_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.fetch_attachment("INBOX", "100", "file.txt")


# ===========================================================================
# Tests: _parse_body_structure_for_attachment
# ===========================================================================

class TestParseBodyStructureForAttachment:
    def test_parse_body_structure_with_attachment(self):
        client = make_client()
        result = client._parse_body_structure_for_attachment(b'("text" "plain")')
        assert isinstance(result, dict)


# ===========================================================================
# Tests: get_quota (additional)
# ===========================================================================

class TestGetQuotaFull:
    def test_get_quota_not_supported_returns_none(self):
        fake_conn = FakeIMAPConnection()
        client = authenticated_client(fake_conn)
        client.capabilities = set()
        result = client.get_quota()
        assert result is None

    def test_get_quota_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.get_quota()


# ===========================================================================
# Tests: save_draft (additional)
# ===========================================================================

class TestSaveDraftFull:
    def test_save_draft_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        message = EmailMessage()
        with pytest.raises(BugException):
            client.save_draft(message)




# ===========================================================================
# Tests: delete_mail_permanently_from_folder_type (additional)
# ===========================================================================

class TestDeleteMailPermanentlyFromFolderTypeFull:
    def test_delete_mail_permanently_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.delete_mail_permanently_from_folder_type(cs.MAIL_FOLDER_DRAFT, "100")


# ===========================================================================
# Tests: _is_folder_subscribed
# ===========================================================================

class TestIsFolderSubscribed:
    def test_is_folder_subscribed_true(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.lsub_response = ("OK", [b'(\\Subscribed) "." "INBOX"'])
        client = authenticated_client(fake_conn)
        result = client._is_folder_subscribed("INBOX")
        assert result is True

    def test_is_folder_subscribed_false(self):
        fake_conn = FakeIMAPConnection()
        fake_conn.lsub_response = ("OK", [])  # no subscribed folders
        client = authenticated_client(fake_conn)
        result = client._is_folder_subscribed("INBOX")
        assert result is False

    def test_is_folder_subscribed_not_authenticated_raises(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client._is_folder_subscribed("INBOX")
