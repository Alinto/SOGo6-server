import pytest
from app.manager.mail.ClientImap import ClientImap
from app.utils.exceptions import RequestException

class FakeIMAPConn:
    """
    Fake IMAP connection.
    """
    def __init__(self, create_typ='OK', delete_typ='OK', list_typ='OK', list_boxes=None):
        self.create_typ = create_typ
        self.created_folders = []
        self.delete_typ = delete_typ
        self.deleted_folders = []
        self.list_typ = list_typ
        self.mailbox_list = list_boxes or [b'INBOX', b'OtherBox']
        self.selected_mailbox = None
        self.select_typ = 'OK'
        self.expunge_typ = 'OK'
        self.expunged = False

    def create(self, folder_name):
        """
        Create a new folder.
        """
        self.created_folders.append(folder_name)
        return (self.create_typ, [b''])

    # For delete_folder
    def delete(self, folder_name):
        """
        Delete a folder.
        """
        self.deleted_folders.append(folder_name)
        return (self.delete_typ, [b''])

    # For list_mailboxes
    def list(self):
        """
        List all mailboxes.
        """
        return (self.list_typ, self.mailbox_list)

    # For expunge_folder
    def select(self, mailbox):
        """
        Select a mailbox.
        """
        self.selected_mailbox = mailbox
        return (self.select_typ, [b''])

    def expunge(self):
        """
        Permanently remove messages marked for deletion.
        """
        if self.expunge_typ == 'OK':
            self.expunged = True
            return ('OK', [b''])
        else:
            return (self.expunge_typ, [b'fail'])


# --- create_folder ---

def test_given_connected_when_create_folder_then_success():
    """
    Test creating a folder when connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn(create_typ='OK')
    client.connection = fake_conn
    # When
    client.create_folder('TestFolder')
    # Then
    assert 'TestFolder' in fake_conn.created_folders

def test_given_not_connected_when_create_folder_then_request_exception():
    """
    Test creating a folder when NOT connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    client.connection = None
    # When/Then
    with pytest.raises(RequestException, match="Not connected"):
        client.create_folder('TestFolder')

def test_given_connected_when_create_folder_and_imap_returns_no_then_request_exception():
    """
    Test creating a folder when connected but IMAP server returns NO.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn(create_typ='NO')
    client.connection = fake_conn
    # When/Then
    with pytest.raises(RequestException, match="Failed to create folder 'TestFolder'"):
        client.create_folder('TestFolder')


# --- delete_folder ---

def test_given_connected_when_delete_folder_then_success():
    """
    Test deleting a folder when connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn(delete_typ='OK')
    client.connection = fake_conn
    # When
    client.delete_folder('TestFolder')
    # Then
    assert 'TestFolder' in fake_conn.deleted_folders

def test_given_not_connected_when_delete_folder_then_request_exception():
    """
    Test deleting a folder when NOT connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    client.connection = None
    # When/Then
    with pytest.raises(RequestException, match="Not connected"):
        client.delete_folder('TestFolder')

def test_given_connected_when_delete_folder_and_imap_returns_no_then_request_exception():
    """
    Test deleting a folder when connected but IMAP server returns NO.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn(delete_typ='NO')
    client.connection = fake_conn
    # When/Then
    with pytest.raises(RequestException, match="Failed to delete folder 'TestFolder'"):
        client.delete_folder('TestFolder')


# --- list_mailboxes ---

def test_given_connected_when_list_mailboxes_then_success():
    """
    Test listing mailboxes when connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    expected = [b'INBOX', b'OtherBox']
    fake_conn = FakeIMAPConn(list_typ='OK', list_boxes=expected)
    client.connection = fake_conn
    # When
    result = client.list_mailboxes()
    # Then
    assert result == expected

def test_given_not_connected_when_list_mailboxes_then_request_exception():
    """
    Test listing mailboxes when NOT connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    client.connection = None
    # When/Then
    with pytest.raises(RequestException, match="Not connected"):
        client.list_mailboxes()

def test_given_connected_when_list_mailboxes_and_imap_returns_no_then_request_exception():
    """
    Test listing mailboxes when connected but IMAP server returns NO.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn(list_typ='NO')
    client.connection = fake_conn
    # When/Then
    with pytest.raises(RequestException, match="Failed to list mailboxes"):
        client.list_mailboxes()

def test_given_connected_when_list_mailboxes_and_mailbox_list_is_none_then_empty_list():
    """
    Test listing mailboxes when connected but IMAP server returns None for mailbox list.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn(list_typ='OK', list_boxes=None)
    fake_conn.mailbox_list = None
    client.connection = fake_conn
    # When
    result = client.list_mailboxes()
    # Then
    assert result == []

# --- expunge_folder ---

def test_given_connected_when_expunge_folder_then_success():
    """
    Test expunging a mailbox when connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn()
    client.connection = fake_conn
    # When
    client.expunge_folder('INBOX')
    # Then
    assert fake_conn.selected_mailbox == 'INBOX'
    assert fake_conn.expunged is True

def test_given_not_connected_when_expunge_folder_then_request_exception():
    """
    Test expunging a mailbox when NOT connected to the IMAP server.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    client.connection = None
    # When/Then
    with pytest.raises(RequestException, match="Not connected"):
        client.expunge_folder('INBOX')

def test_given_connected_when_expunge_folder_select_fails_then_request_exception():
    """
    Test expunging a mailbox when connected but IMAP server returns NO.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn()
    fake_conn.select_typ = 'NO'
    client.connection = fake_conn
    # When/Then
    with pytest.raises(RequestException, match="Failed to select mailbox INBOX"):
        client.expunge_folder('INBOX')

def test_given_connected_when_expunge_folder_expunge_fails_then_request_exception():
    """
    Test expunging a mailbox when connected but IMAP server returns NO on expunge.
    """
    # Given
    client = ClientImap(server='imap.example.org', port=143)
    fake_conn = FakeIMAPConn()
    fake_conn.expunge_typ = 'NO'
    client.connection = fake_conn
    # When/Then
    with pytest.raises(RequestException, match="Failed to expunge mailbox INBOX"):
        client.expunge_folder('INBOX')
