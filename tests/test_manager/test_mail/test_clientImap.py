"""
Tests unitaires pour ClientImap (Manager layer).
Ces tests utilisent des mock objects pour simuler les réponses IMAP.
"""
from unittest import mock
from app.manager.mail.ClientImap import ClientImap, _convert_rights_to_imap, _convert_imap_to_rights
from app.utils.exceptions import RequestException
from app.utils.constant.api import (
    USERCANVIEWFOLDER, USERCANREADMAILS, USERCANMARKMAILSREAD,
    USERCANINSERTMAILS, USERCANPOSTMAILS, USERCANCREATESUBFOLDERS,
    USERCANREMOVEFOLDER, USERCANERASEMAILS, USERCANEXPUNGEFOLDER,
    USERCANADMINISTRATOR
)


class FakeIMAPConnection:
    """Fake IMAP connection for testing."""
    def __init__(self):
        self.logged_in = False
        self.selected_mailbox = None
        self.folders = {}
        self.login_response = ('OK', [b''])
        self.select_response = ('OK', [b'10'])
        self.create_response = ('OK', [b''])
        self.delete_response = ('OK', [b''])
        self.list_response = ('OK', [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Sent"'])
        self.expunge_response = ('OK', [b'1', b'2'])
        self.uid_response = ('OK', [b''])
        self.fetch_response = ('OK', [(b'1 (UID 100 FLAGS (\\Seen))', b'Subject: Test\r\n\r\nBody')])
        self.getacl_response = ('OK', [b'INBOX user1 lrswipkxtea user2 lr'])
        self.setacl_response = ('OK', [b''])
        self.deleteacl_response = ('OK', [b''])
        
    def login(self, username, password):
        self.logged_in = True
        return self.login_response

    def logout(self):
        self.logged_in = False
        return ('OK', [b''])

    def select(self, mailbox):
        self.selected_mailbox = mailbox
        return self.select_response

    def create(self, folder_name):
        self.folders[folder_name] = True
        return self.create_response

    def delete(self, folder_name):
        if folder_name in self.folders:
            del self.folders[folder_name]
        return self.delete_response

    def list(self, ref='""', pattern='*'):
        return self.list_response

    def expunge(self):
        return self.expunge_response

    def uid(self, command, *args):
        return self.uid_response

    def fetch(self, message_set, parts):
        return self.fetch_response

    def getacl(self, folder_name):
        return self.getacl_response

    def setacl(self, folder_name, identifier, rights):
        return self.setacl_response

    def deleteacl(self, folder_name, identifier):
        return self.deleteacl_response

    def rename(self, old_name, new_name):
        return ('OK', [b''])

    def subscribe(self, folder_name):
        return ('OK', [b''])

    def unsubscribe(self, folder_name):
        return ('OK', [b''])

    def lsub(self, ref, pattern):
        return ('OK', [b'(\\HasNoChildren) "/" "INBOX"'])


# ========== Tests for rights conversion ==========

def test_convert_rights_to_imap_with_all_rights():
    """Test converting all SOGo rights to IMAP string."""
    rights_dict = {
        USERCANVIEWFOLDER: 1,
        USERCANREADMAILS: 1,
        USERCANMARKMAILSREAD: 1,
        USERCANINSERTMAILS: 1,
        USERCANPOSTMAILS: 1,
        USERCANCREATESUBFOLDERS: 1,
        USERCANREMOVEFOLDER: 1,
        USERCANERASEMAILS: 1,
        USERCANEXPUNGEFOLDER: 1,
        USERCANADMINISTRATOR: 1
    }
    result = _convert_rights_to_imap(rights_dict)
    assert 'l' in result
    assert 'r' in result
    assert 's' in result
    assert 'w' in result
    assert 'i' in result
    assert 'p' in result
    assert 'k' in result
    assert 'x' in result
    assert 't' in result
    assert 'e' in result
    assert 'a' in result


def test_convert_rights_to_imap_with_empty_dict():
    """Test converting empty rights dict."""
    assert _convert_rights_to_imap({}) == ""


def test_convert_imap_to_rights_with_full_string():
    """Test converting full IMAP rights string to SOGo dict."""
    imap_rights = "lrswipkxtea"
    result = _convert_imap_to_rights(imap_rights)
    assert result[USERCANVIEWFOLDER] == 1
    assert result[USERCANREADMAILS] == 1
    assert result[USERCANMARKMAILSREAD] == 1
    assert result[USERCANINSERTMAILS] == 1
    assert result[USERCANPOSTMAILS] == 1
    assert result[USERCANCREATESUBFOLDERS] == 1
    assert result[USERCANREMOVEFOLDER] == 1
    assert result[USERCANERASEMAILS] == 1
    assert result[USERCANEXPUNGEFOLDER] == 1
    assert result[USERCANADMINISTRATOR] == 1


def test_convert_imap_to_rights_with_empty_string():
    """Test converting empty IMAP rights string."""
    result = _convert_imap_to_rights("")
    for value in result.values():
        assert value == 0


# ========== Tests for connection and login ==========

def test_login_success(monkeypatch):
    """Test successful login."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)

    with mock.patch('imaplib.IMAP4', return_value=fake_conn):
        client.login('user@example.com', 'password')
        assert fake_conn.logged_in is True


def test_login_with_invalid_credentials(monkeypatch):
    """Test login with invalid credentials."""
    fake_conn = FakeIMAPConnection()
    fake_conn.login_response = ('NO', [b'Invalid credentials'])
    client = ClientImap(server='imap.example.com', port=143)

    with mock.patch('imaplib.IMAP4', return_value=fake_conn):
        with pytest.raises(RequestException, match="Failed to login"):
            client.login('user@example.com', 'wrong_password')


def test_logout_success():
    """Test successful logout."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.logout()
    assert fake_conn.logged_in is False


# ========== Tests for mailbox operations ==========

def test_select_mailbox_success():
    """Test selecting a mailbox."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'42'])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    count = client.select_mailbox('INBOX')
    assert count == 42
    assert fake_conn.selected_mailbox == 'INBOX'


def test_select_mailbox_not_connected():
    """Test selecting mailbox when not connected."""
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = None

    with pytest.raises(RequestException, match="Not connected"):
        client.select_mailbox('INBOX')


def test_create_folder_success():
    """Test creating a folder."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.create_folder('TestFolder')
    assert 'TestFolder' in fake_conn.folders


def test_create_folder_failure():
    """Test folder creation failure."""
    fake_conn = FakeIMAPConnection()
    fake_conn.create_response = ('NO', [b'Folder already exists'])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    with pytest.raises(RequestException, match="Failed to create folder"):
        client.create_folder('ExistingFolder')


def test_delete_folder_success():
    """Test deleting a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.folders = {'TestFolder': True}
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.delete_folder('TestFolder')
    assert 'TestFolder' not in fake_conn.folders


def test_list_mailboxes_success():
    """Test listing mailboxes."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    result = client.list_mailboxes()
    assert len(result) == 2
    assert isinstance(result[0], bytes)


# ========== Tests for mail operations ==========

def test_uid_copy_success():
    """Test copying a mail by UID."""
    fake_conn = FakeIMAPConnection()
    fake_conn.uid_response = ('OK', [b''])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.uid_copy(100, 'Trash')
    # No exception means success


def test_uid_copy_with_invalid_uid():
    """Test copying mail with invalid UID."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    with pytest.raises(RequestException, match="Invalid mail UID"):
        client.uid_copy(0, 'Trash')


def test_uid_store_flags_success():
    """Test storing flags on a mail."""
    fake_conn = FakeIMAPConnection()
    fake_conn.uid_response = ('OK', [b''])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

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
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    mails, total = client.fetch_mails('INBOX', number_of_mails=2)
    assert total == 10
    assert len(mails) == 2


def test_fetch_mail_success():
    """Test fetching a single mail by UID."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.uid_response = ('OK', [(b'1 (UID 100)', b'Subject: Test\r\n\r\nBody')])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    mail_bytes = client.fetch_mail('INBOX', 100)
    assert mail_bytes == b'Subject: Test\r\n\r\nBody'


def test_delete_mail_by_uid_success():
    """Test deleting a mail by UID."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.uid_response = ('OK', [b''])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.delete_mail_by_uid('INBOX', 100)
    # No exception means success


def test_expunge_folder_success():
    """Test expunging a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.expunge_response = ('OK', [b'1', b'2', b'3'])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    count = client.expunge_folder('INBOX')
    assert count == 3


# ========== Tests for ACL operations ==========

def test_get_acl_success():
    """Test getting ACL for a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.getacl_response = ('OK', [b'INBOX user1 lrswipkxtea user2 lr'])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    acl_list = client.get_acl('INBOX')
    assert len(acl_list) == 2
    assert acl_list[0][0] == 'user1'
    assert acl_list[1][0] == 'user2'


def test_set_acl_success():
    """Test setting ACL for a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.setacl_response = ('OK', [b''])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    rights = {USERCANVIEWFOLDER: 1, USERCANREADMAILS: 1}
    client.set_acl('INBOX', 'user@example.com', rights)
    # No exception means success


def test_delete_acl_success():
    """Test deleting ACL for a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.deleteacl_response = ('OK', [b''])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.delete_acl('INBOX', 'user@example.com')
    # No exception means success


# ========== Tests for folder details ==========

def test_get_folder_details_success():
    """Test getting folder details."""
    fake_conn = FakeIMAPConnection()
    fake_conn.list_response = ('OK', [b'(\\HasNoChildren) "/" "INBOX"'])
    fake_conn.lsub_response = ('OK', [b'(\\HasNoChildren) "/" "INBOX"'])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    details = client.get_folder_details('INBOX')
    assert details['name'] == 'INBOX'
    assert details['path'] == 'INBOX'
    assert details['subscribed'] == 1


def test_rename_folder_success():
    """Test renaming a folder."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.rename_folder('OldName', 'NewName')
    # No exception means success


def test_subscribe_folder_success():
    """Test subscribing to a folder."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.subscribe_folder('INBOX')
    # No exception means success


def test_unsubscribe_folder_success():
    """Test unsubscribing from a folder."""
    fake_conn = FakeIMAPConnection()
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    client.unsubscribe_folder('INBOX')
    # No exception means success


def test_purge_folder_success():
    """Test purging a folder."""
    fake_conn = FakeIMAPConnection()
    fake_conn.select_response = ('OK', [b'10'])
    fake_conn.uid_response = ('OK', [b'1 2 3'])
    client = ClientImap(server='imap.example.com', port=143)
    client.connection = fake_conn

    # Mock get_mail_uids_before_date to return some UIDs
    with mock.patch.object(client, 'get_mail_uids_before_date', return_value=[1, 2, 3]):
        count = client.purge_folder('INBOX')
        assert count == 3
