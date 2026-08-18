"""
Tests unitaires pour ModuleMail (Module layer).
Ces tests utilisent un fake ClientMailServer pour tester la logique mtier du module.
"""
import pytest
from io import BytesIO
from unittest.mock import MagicMock
from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


ACCOUNT_ID = "default"


class FakeClientMailServer:
    """Fake ClientMailServer for testing ModuleMail."""

    def __init__(self):
        # Configurable results
        self.list_folders_result = [
            {'name': 'INBOX', 'path': 'INBOX'},
            {'name': 'Sent', 'path': 'Sent'}
        ]
        self.get_one_folder_result = {
            'name': 'INBOX',
            'path': 'INBOX',
            'type': 'inbox',
            'subscribed': 1,
            'children': []
        }
        self.create_folder_result = None   # None = success, Exception instance = raises
        self.delete_folder_result = None
        self.expunge_folder_result = 5
        self.purge_folder_result = 10
        self.fetch_mail_result = None   # set per test
        self.fetch_mail_raw_result = 'Subject: Test\r\n\r\nBody'
        self.get_acl_result = [('user1@example.com', {'userCanViewFolder': 1})]

        # Call tracking
        self.create_folder_calls = []
        self.delete_folder_calls = []
        self.copy_mail_to_mailbox_calls = []
        self.add_flags_calls = []
        self.remove_flags_calls = []
        self.delete_mails_by_uid_calls = []
        self.set_acl_calls = []
        self.delete_acl_calls = []

    # ---- folder methods ----

    def list_folders(self):
        return self.list_folders_result

    def get_one_folder(self, folder_path):
        return self.get_one_folder_result

    def create_folder(self, folder_name, parent_path=None):
        self.create_folder_calls.append((folder_name, parent_path))
        if self.create_folder_result is not None:
            raise self.create_folder_result
        return folder_name  # returns the new folder path

    def delete_folder(self, folder_path, do_children=True):
        self.delete_folder_calls.append((folder_path, do_children))
        if self.delete_folder_result is not None:
            raise self.delete_folder_result

    def rename_folder(self, folder_path, new_name):
        """Rename a folder."""
        # No error handling needed for basic case
        return new_name

    def change_folder_type(self, folder_path, new_type):
        """Change the type of a folder."""
        # No error handling needed for basic case
        return new_type

    def expunge_folder(self, folder_path, do_subfolders=True):
        return self.expunge_folder_result

    def purge_folder(self, folder_path, before_date=None, do_children=False, permanently=False):
        return self.purge_folder_result

    # ---- mail methods ----

    def fetch_all_mails_with_content(self, folder_name, number_of_mails, offset=0):
        """Returns an iterator: first item has {'nb_mails': int}, then mail dicts."""
        yield {'nb_mails': 0}

    def fetch_mail(self, folder_name, mail_uid):
        if self.fetch_mail_result is not None:
            return self.fetch_mail_result
        return {
            'uid': str(mail_uid),
            'mail': _make_email_message(),
            'flags': {
                'seen': False,
                'flagged': False,
                'answered': False,
                'forwarded': False,
                'deleted': False,
                'all': []
            },
            'size': 100
        }

    def fetch_mail_raw(self, folder_name, mail_uid):
        return self.fetch_mail_raw_result

    def delete_mails_by_uid(self, folder_path, mail_uids, move_to_trash=True, permanently=True):
        self.delete_mails_by_uid_calls.append((folder_path, mail_uids))

    def copy_mail_to_mailbox(self, src_folder, mail_uid, dest_folder, create_dest=False):
        self.copy_mail_to_mailbox_calls.append((src_folder, mail_uid, dest_folder))

    def add_flags_to_mail(self, folder_name, mail_uid, flags):
        self.add_flags_calls.append((folder_name, mail_uid, flags))

    def remove_flags_to_mail(self, folder_name, mail_uid, flags):
        self.remove_flags_calls.append((folder_name, mail_uid, flags))

    # ---- ACL methods ----

    def get_acl(self, folder_path):
        return self.get_acl_result

    def set_acl(self, folder_path, identifier, rights):
        self.set_acl_calls.append((folder_path, identifier, rights))

    def delete_acl(self, folder_name, identifier):
        """Delete ACL for a folder."""
        self.delete_acl_calls.append((folder_name, identifier))

    def get_mail_uids_before_date(self, mailbox, before_date=None, exclude_deleted=True):
        """Get mail UIDs in a mailbox before a certain date."""
        if before_date:
            return [1, 2, 3]
        return [1, 2, 3, 4, 5]

    def delete_mail_by_uid(self, mailbox, mail_uid):
        """Delete a mail by its UID."""
        self.delete_mails_by_uid_calls.append((mailbox, mail_uid))

    def is_folder_in_trash(self, folder_name):
        """Check if a folder is within the Trash folder hierarchy."""
        if not folder_name:
            return False
        folder_lower = folder_name.lower()
        return folder_lower == 'trash' or folder_lower.startswith('trash/')

    def list_mailboxes_detailed(self):
        """Return detailed mailbox list."""
        return [
            {'name': 'INBOX', 'path': 'INBOX'},
            {'name': 'Sent', 'path': 'Sent'}
        ]

    def fetch_all_mails_without_content(self, mailbox, number_of_mails, offset=0):
        """Fetch all mails from a mailbox without content (used by get_folder_mails)."""
        yield {'nb_mails': 0}

    def fetch_attachment(self, folder_name, mail_uid, filename):
        """Fetch an attachment from a mail."""
        return (b"attachment data", "application/octet-stream")

    def delete_mail_permanently_from_folder_type(self, folder_type, uid):
        """Delete a mail permanently from a folder type."""
        pass


def _make_email_message(subject='Test', from_='sender@example.com',
                         to='recipient@example.com',
                         date='Mon, 1 Jan 2024 10:00:00 +0000',
                         body='Body content'):
    """Build a minimal email.message.Message for parsing."""
    from email.message import Message
    msg = Message()
    msg['Subject'] = subject
    msg['From'] = from_
    msg['To'] = to
    msg['Date'] = date
    msg.set_payload(body)
    msg.set_type('text/plain')
    return msg


def _make_module(monkeypatch, fake_client=None):
    """Create a ModuleMail with mocked User/MailSettings and patched _open_client_for."""
    if fake_client is None:
        fake_client = FakeClientMailServer()

    mock_user = MagicMock()
    mock_user.login_mail_server = 'user@example.com'
    mock_user.uid = 'test_user_123'
    mock_user.profile.preferences.get.return_value = {}
    mock_mail_settings = MagicMock()
    mock_process_setting = MagicMock()

    module = ModuleMail(user=mock_user, mail_settings=mock_mail_settings, process_setting=mock_process_setting)
    # Patch _open_client_for to always return our fake client
    monkeypatch.setattr(module, '_open_client_for', lambda account_id, do_login=True: fake_client)
    # Patch _get_db to return a mock DB client
    mock_db = MagicMock()
    monkeypatch.setattr(module, '_get_db', lambda: mock_db)
    return module, fake_client


# ========== Tests for initialization ==========

def test_module_init_success():
    """Test ModuleMail initialization with valid mocked objects."""
    mock_user = MagicMock()
    mock_mail_settings = MagicMock()
    module = ModuleMail(user=mock_user, mail_settings=mock_mail_settings)
    assert module.user is mock_user
    assert module.mail_settings is mock_mail_settings


def test_module_init_without_user_raises():
    """Test ModuleMail initialization without arguments raises TypeError."""
    with pytest.raises(TypeError):
        ModuleMail()


# ========== Tests for get_folder_list ==========

def test_get_folder_list_success(monkeypatch):
    """Test getting folder list."""
    module, fake_client = _make_module(monkeypatch)

    result = module.get_folder_list(ACCOUNT_ID)
    assert len(result) == 2
    assert result[0]['name'] == 'INBOX'
    assert result[1]['name'] == 'Sent'


def test_get_folder_list_with_client_error(monkeypatch):
    """Test folder list retrieval with client error."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.list_folders = lambda: (_ for _ in ()).throw(RequestException("Connection failed"))

    with pytest.raises(RequestException, match="Connection failed"):
        module.get_folder_list(ACCOUNT_ID)


# ========== Tests for create_folder ==========

def test_create_folder_success(monkeypatch):
    """Test creating a folder."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.get_one_folder_result = {
        'name': 'NewFolder',
        'path': 'NewFolder',
        'type': 'folder',
        'subscribed': 1,
        'children': []
    }

    result = module.create_folder(ACCOUNT_ID, "NewFolder", parent_path=None)
    assert result['name'] == "NewFolder"
    assert any(call[0] == "NewFolder" for call in fake_client.create_folder_calls)


def test_create_folder_with_client_error(monkeypatch):
    """Test folder creation with client error."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.create_folder_result = RequestException("Folder already exists")

    with pytest.raises(RequestException, match="Folder already exists"):
        module.create_folder(ACCOUNT_ID, "ExistingFolder", parent_path=None)


# ========== Tests for delete_folder ==========

def test_delete_folder_success(monkeypatch):
    """Test deleting a folder succeeds (delegates to client)."""
    module, fake_client = _make_module(monkeypatch)

    module.delete_folder(ACCOUNT_ID, "OldFolder")

    assert any(call[0] == "OldFolder" for call in fake_client.delete_folder_calls)


def test_delete_folder_with_client_error(monkeypatch):
    """Test deleting a folder propagates client error."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.delete_folder_result = RequestException("Folder not found")

    with pytest.raises(RequestException, match="Folder not found"):
        module.delete_folder(ACCOUNT_ID, "NonExistent")


# ========== Tests for get_folder_mails ==========

def test_get_folder_mails_success(monkeypatch):
    """Test getting mails from a folder."""
    module, fake_client = _make_module(monkeypatch)

    mail1 = _make_email_message(subject='Test1')
    mail2 = _make_email_message(subject='Test2')

    def fetch_all(folder_name, number_of_mails, offset=0):
        yield {'nb_mails': 100}
        yield {'uid': '1', 'mail': mail1, 'flags': {'seen': True, 'flagged': False, 'answered': False, 'forwarded': False, 'deleted': False, 'all': ['\\Seen']}, 'size': 120}
        yield {'uid': '2', 'mail': mail2, 'flags': {'seen': False, 'flagged': False, 'answered': False, 'forwarded': False, 'deleted': False, 'all': []}, 'size': 120}

    fake_client.fetch_all_mails_with_content = fetch_all

    result, total = module.get_folder_mails(ACCOUNT_ID, "INBOX", CollectionPaginateArgs(page=1, page_size=10))
    assert total == 100
    assert len(result) == 2
    assert result[0]['subject'] == 'Test1'
    assert result[0]['seen'] is True
    assert result[1]['seen'] is False


def test_get_folder_mails_empty_folder(monkeypatch):
    """Test getting mails from empty folder."""
    module, fake_client = _make_module(monkeypatch)

    def fetch_all(folder_name, number_of_mails, offset=0):
        yield {'nb_mails': 0}

    fake_client.fetch_all_mails_with_content = fetch_all

    result, total = module.get_folder_mails(ACCOUNT_ID, "INBOX", CollectionPaginateArgs(page=1, page_size=10))
    assert total == 0
    assert len(result) == 0


# ========== Tests for delete_mails ==========

def test_delete_mails_success(monkeypatch):
    """Test deleting multiple mails."""
    module, fake_client = _make_module(monkeypatch)

    module.delete_mails(ACCOUNT_ID, "INBOX", [1, 2, 3])
    assert len(fake_client.delete_mails_by_uid_calls) == 1
    assert fake_client.delete_mails_by_uid_calls[0] == ("INBOX", [1, 2, 3])


def test_delete_mails_client_error(monkeypatch):
    """Test deleting mails propagates client error."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(folder_path, mail_uids, move_to_trash=True, permanently=True):
        raise RequestException("Delete failed")

    fake_client.delete_mails_by_uid = raise_error

    with pytest.raises(RequestException, match="Delete failed"):
        module.delete_mails(ACCOUNT_ID, "INBOX", [1, 2, 3])


# ========== Tests for expunge_folder ==========

def test_expunge_folder_success(monkeypatch):
    """Test expunging a folder."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.expunge_folder_result = 5

    result = module.expunge_folder(ACCOUNT_ID, "INBOX")
    assert result['mail_deleted'] == 5


# ========== Tests for purge_folder_mails ==========

def test_purge_folder_mails_success(monkeypatch):
    """Test purging folder mails."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.purge_folder_result = 10

    purge_data = {"do_subfolders": False, "permanently_delete": False, "date": None}
    result = module.purge_folder_mails(ACCOUNT_ID, "INBOX", purge_data)
    assert result['mails_deleted'] == 10


def test_purge_folder_mails_with_subfolders(monkeypatch):
    """Test purging folder mails including subfolders."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.purge_folder_result = 15

    purge_data = {"do_subfolders": True, "permanently_delete": False, "date": None}
    result = module.purge_folder_mails(ACCOUNT_ID, "INBOX", purge_data)
    assert result['mails_deleted'] == 15


def test_purge_folder_mails_with_date_filter(monkeypatch):
    """Test purging folder mails with date filter."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.purge_folder_result = 3

    purge_data = {"do_subfolders": False, "permanently_delete": False, "date": "2024-01-01"}
    result = module.purge_folder_mails(ACCOUNT_ID, "INBOX", purge_data)
    assert result['mails_deleted'] == 3


def test_purge_folder_mails_with_permanent_delete(monkeypatch):
    """Test purging folder mails with permanent deletion."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.purge_folder_result = 10

    purge_data = {"do_subfolders": False, "permanently_delete": True, "date": None}
    result = module.purge_folder_mails(ACCOUNT_ID, "INBOX", purge_data)
    assert result['mails_deleted'] == 10


# ========== Tests for get_one_folder ==========

def test_get_one_folder_success(monkeypatch):
    """Test getting folder details."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.get_one_folder_result = {
        'name': 'INBOX',
        'path': 'INBOX',
        'type': 'inbox',
        'subscribed': 1,
        'total': 100,
        'unread': 10,
        'children': []
    }

    result = module.get_one_folder(ACCOUNT_ID, "INBOX")
    assert result['name'] == 'INBOX'
    assert result['path'] == 'INBOX'
    assert result['type'] == 'inbox'
    assert result['subscribed'] == 1
    assert result['total'] == 100
    assert result['unread'] == 10


def test_get_one_folder_with_children(monkeypatch):
    """Test getting folder details with children."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.get_one_folder_result = {
        'name': 'Archive',
        'path': 'Archive',
        'type': 'folder',
        'subscribed': 1,
        'children': [
            {'name': '2024', 'path': 'Archive/2024'},
            {'name': '2023', 'path': 'Archive/2023'}
        ]
    }

    result = module.get_one_folder(ACCOUNT_ID, "Archive")
    assert result['name'] == 'Archive'
    assert len(result['children']) == 2


# ========== Tests for get_mail_detail ==========

def test_get_mail_detail_success(monkeypatch):
    """Test getting mail details."""
    module, fake_client = _make_module(monkeypatch)

    result = module.get_mail_detail(ACCOUNT_ID, "INBOX", "42")
    assert result['uid'] == "42"
    assert result['subject'] == 'Test'
    assert 'contents' in result
    assert isinstance(result['contents'], list)
    assert 'from' in result
    assert 'to' in result
    assert 'attachments' in result
    assert isinstance(result['attachments'], list)


# ========== Tests for get_mail_raw ==========

def test_get_mail_raw_success(monkeypatch):
    """Test getting raw mail content."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.fetch_mail_raw_result = 'Subject: Test\r\n\r\nBody'

    result = module.get_mail_raw(ACCOUNT_ID, "INBOX", "42")
    assert result['raw'] == 'Subject: Test\r\n\r\nBody'


# ========== Tests for get_folder_share ==========

def test_get_folder_share_success(monkeypatch):
    """Test getting folder share information (yields tuples)."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.get_acl_result = [
        ('user1@example.com', {'userCanViewFolder': 1, 'userCanReadMails': 1}),
        ('anyone', {'userCanViewFolder': 1})
    ]

    result = list(module.get_folder_share(ACCOUNT_ID, "INBOX"))
    identifiers = [item[0] for item in result]
    assert 'user1@example.com' in identifiers
    assert 'anyone' in identifiers


# ========== Tests for share_folder ==========

def test_share_folder_success(monkeypatch):
    """Test sharing a folder with users."""
    module, fake_client = _make_module(monkeypatch)
    module.user.login_mail_server = 'owner@example.com'
    fake_client.get_acl_result = []

    def get_acl_after_share(folder_path):
        if fake_client.set_acl_calls:
            return [('user1@example.com', {'userCanViewFolder': 1, 'userCanReadMails': 1})]
        return []

    fake_client.get_acl = get_acl_after_share

    share_data = [
        {
            "c_email": "user1@example.com",
            "rights": {"userCanViewFolder": 1, "userCanReadMails": 1}
        }
    ]

    result = list(module.share_folder(ACCOUNT_ID, "INBOX", share_data))
    assert len(fake_client.set_acl_calls) >= 1
    # share_folder yields (identifier, rights) tuples
    assert any(item[0] == 'user1@example.com' for item in result)


# ========== Tests for rename_folder ==========

def test_rename_folder_success(monkeypatch):
    """Test renaming a folder successfully."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.get_one_folder_result = {
        'name': 'RenamedFolder',
        'path': 'RenamedFolder',
        'type': 'folder',
        'subscribed': 1
    }

    result = module.rename_folder(ACCOUNT_ID, "OldFolder", "RenamedFolder")
    
    assert result['name'] == 'RenamedFolder'
    assert result['path'] == 'RenamedFolder'


def test_rename_folder_with_client_error(monkeypatch):
    """Test renaming a folder with client error."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Cannot rename folder")

    # Mock the rename operation to fail
    fake_client.rename_folder = raise_error

    with pytest.raises(RequestException, match="Cannot rename folder"):
        module.rename_folder(ACCOUNT_ID, "INBOX", "NewName")


# ========== Tests for change_folder_type ==========

def test_change_folder_type_success(monkeypatch):
    """Test changing folder type successfully."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.get_one_folder_result = {
        'name': 'Archive',
        'path': 'Archive',
        'type': 'NORMAL', 
        'subscribed': 1
    }

    result = module.change_folder_type(ACCOUNT_ID, "Archive", "JUNK")
    
    assert result['name'] == 'Archive'
    # Result type will be the one from get_one_folder called again, which is 'folder'
    # since we're not updating fake_client between calls


def test_change_folder_type_with_client_error(monkeypatch):
    """Test changing folder type with client error."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Cannot change folder type")

    fake_client.get_one_folder = raise_error

    with pytest.raises(RequestException, match="Cannot change folder type"):
        module.change_folder_type(ACCOUNT_ID, "INBOX", "JUNK")


# ========== Tests for perform_mail_action ==========

def test_perform_mail_action_tag_single_tag(monkeypatch):
    """Test tagging a mail with a single tag."""
    module, fake_client = _make_module(monkeypatch)

    action_data = {"action": "tag", "data": "Important"}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "tag"
    assert result["mail_uid"] == "42"
    assert result["tags_added"] == ["Important"]
    assert ("INBOX", "42", ["Important"]) in fake_client.add_flags_calls


def test_perform_mail_action_tag_multiple_tags(monkeypatch):
    """Test tagging a mail with multiple tags."""
    module, fake_client = _make_module(monkeypatch)

    action_data = {"action": "tag", "data": ["Important", "Work"]}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "tag"
    assert result["tags_added"] == ["Important", "Work"]
    assert ("INBOX", "42", ["Important", "Work"]) in fake_client.add_flags_calls


def test_perform_mail_action_tag_missing_data(monkeypatch):
    """Test tagging without providing tags data."""
    module, _ = _make_module(monkeypatch)

    action_data = {"action": "tag"}
    with pytest.raises(RequestException, match="Missing tags data for tag action"):
        module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)


def test_perform_mail_action_untag_single_tag(monkeypatch):
    """Test untagging a mail with a single tag."""
    module, fake_client = _make_module(monkeypatch)

    action_data = {"action": "untag", "data": "Important"}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "untag"
    assert result["mail_uid"] == "42"
    assert result["tags_removed"] == ["Important"]
    assert ("INBOX", "42", ["Important"]) in fake_client.remove_flags_calls


def test_perform_mail_action_untag_multiple_tags(monkeypatch):
    """Test untagging a mail with multiple tags."""
    module, fake_client = _make_module(monkeypatch)

    action_data = {"action": "untag", "data": ["Important", "Work"]}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "untag"
    assert result["tags_removed"] == ["Important", "Work"]
    assert ("INBOX", "42", ["Important", "Work"]) in fake_client.remove_flags_calls


def test_perform_mail_action_move_success(monkeypatch):
    """Test moving a mail to another folder."""
    module, fake_client = _make_module(monkeypatch)

    action_data = {"action": "move", "data": "Archive"}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "move"
    assert result["mail_uid"] == "42"
    assert result["from_folder"] == "INBOX"
    assert result["to_folder"] == "Archive"
    assert ("INBOX", "42", "Archive") in fake_client.copy_mail_to_mailbox_calls
    assert ("INBOX", "42", ['\\Deleted']) in fake_client.add_flags_calls


def test_perform_mail_action_move_missing_destination(monkeypatch):
    """Test moving without providing destination folder."""
    module, _ = _make_module(monkeypatch)

    action_data = {"action": "move"}
    with pytest.raises(RequestException, match="Missing or invalid destination folder for move action"):
        module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)


def test_perform_mail_action_spam_success(monkeypatch):
    """Test marking a mail as spam."""
    module, fake_client = _make_module(monkeypatch)
    # domain_mail_folder_name is empty by default so "Junk" is the fallback
    module.domain_mail_folder_name = {}

    action_data = {"action": "spam"}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "spam"
    assert result["mail_uid"] == "42"
    assert result["moved_to"] == "Junk"
    assert ("INBOX", "42", "Junk") in fake_client.copy_mail_to_mailbox_calls
    assert ("INBOX", "42", ['\\Deleted']) in fake_client.add_flags_calls


def test_perform_mail_action_ham_success(monkeypatch):
    """Test marking a mail as ham (not spam)."""
    module, fake_client = _make_module(monkeypatch)
    module.domain_mail_folder_name = {}

    action_data = {"action": "ham"}
    result = module.perform_mail_action(ACCOUNT_ID, "Junk", "42", action_data)

    assert result["action"] == "ham"
    assert result["mail_uid"] == "42"
    assert result["moved_to"] == "INBOX"
    assert ("Junk", "42", "INBOX") in fake_client.copy_mail_to_mailbox_calls
    assert ("Junk", "42", ['\\Deleted']) in fake_client.add_flags_calls


def test_perform_mail_action_copy_success(monkeypatch):
    """Test copying a mail to another folder."""
    module, fake_client = _make_module(monkeypatch)

    action_data = {"action": "copy", "data": "Archive"}
    result = module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)

    assert result["action"] == "copy"
    assert result["mail_uid"] == "42"
    assert result["from_folder"] == "INBOX"
    assert result["to_folder"] == "Archive"
    assert ("INBOX", "42", "Archive") in fake_client.copy_mail_to_mailbox_calls
    # Copy should NOT delete the original mail
    assert ("INBOX", "42", ['\\Deleted']) not in fake_client.add_flags_calls


def test_perform_mail_action_copy_missing_destination(monkeypatch):
    """Test copying without providing destination folder."""
    module, _ = _make_module(monkeypatch)

    action_data = {"action": "copy"}
    with pytest.raises(RequestException, match="Missing or invalid destination folder for copy action"):
        module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)


def test_perform_mail_action_invalid_action(monkeypatch):
    """Test handling of invalid action."""
    module, _ = _make_module(monkeypatch)

    action_data = {"action": "invalid_action"}
    with pytest.raises(RequestException, match="Invalid action: invalid_action"):
        module.perform_mail_action(ACCOUNT_ID, "INBOX", "42", action_data)


# ========== Tests for perform_mail_batch_action ==========

def test_perform_mail_batch_action_tag_single_tag(monkeypatch):
    """Test batch-tagging multiple mails with a single tag."""
    module, fake_client = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "tag", "data": "Important"}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "tag"
    assert result["mail_uid"] == ["42", "43"]
    assert result["tags_added"] == ["Important"]
    assert ("INBOX", ["42", "43"], ["Important"]) in fake_client.add_flags_calls


def test_perform_mail_batch_action_tag_multiple_tags(monkeypatch):
    """Test batch-tagging multiple mails with multiple tags."""
    module, fake_client = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "tag", "data": ["Important", "Work"]}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "tag"
    assert result["tags_added"] == ["Important", "Work"]
    assert ("INBOX", ["42", "43"], ["Important", "Work"]) in fake_client.add_flags_calls


def test_perform_mail_batch_action_tag_missing_data(monkeypatch):
    """Test batch-tagging without providing tags data."""
    module, _ = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "tag"}
    with pytest.raises(RequestException, match="Missing tags data for tag action"):
        module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)


def test_perform_mail_batch_action_untag_single_tag(monkeypatch):
    """Test batch-untagging multiple mails with a single tag."""
    module, fake_client = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "untag", "data": "Important"}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "untag"
    assert result["mail_uid"] == ["42", "43"]
    assert result["tags_removed"] == ["Important"]
    assert ("INBOX", ["42", "43"], ["Important"]) in fake_client.remove_flags_calls


def test_perform_mail_batch_action_untag_multiple_tags(monkeypatch):
    """Test batch-untagging multiple mails with multiple tags."""
    module, fake_client = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "untag", "data": ["Important", "Work"]}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "untag"
    assert result["tags_removed"] == ["Important", "Work"]
    assert ("INBOX", ["42", "43"], ["Important", "Work"]) in fake_client.remove_flags_calls


def test_perform_mail_batch_action_untag_missing_data(monkeypatch):
    """Test batch-untagging without providing tags data."""
    module, _ = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "untag"}
    with pytest.raises(RequestException, match="Missing tags data for untag action"):
        module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)


def test_perform_mail_batch_action_move_success(monkeypatch):
    """Test batch-moving multiple mails to another folder in a single IMAP call."""
    module, fake_client = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "move", "data": "Archive"}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "move"
    assert result["mail_uid"] == ["42", "43"]
    assert result["from_folder"] == "INBOX"
    assert result["to_folder"] == "Archive"
    assert ("INBOX", ["42", "43"], "Archive") in fake_client.copy_mail_to_mailbox_calls
    assert ("INBOX", ["42", "43"], ['\\Deleted']) in fake_client.add_flags_calls


def test_perform_mail_batch_action_move_missing_destination(monkeypatch):
    """Test batch-moving without providing destination folder."""
    module, _ = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "move"}
    with pytest.raises(RequestException, match="Missing or invalid destination folder for move action"):
        module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)


def test_perform_mail_batch_action_spam_success(monkeypatch):
    """Test batch-marking multiple mails as spam in a single IMAP call."""
    module, fake_client = _make_module(monkeypatch)
    # domain_mail_folder_name is empty by default so "Junk" is the fallback
    module.domain_mail_folder_name = {}

    batch_action_data = {"uids": [42, 43], "action": "spam"}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "spam"
    assert result["mail_uid"] == ["42", "43"]
    assert result["moved_to"] == "Junk"
    assert ("INBOX", ["42", "43"], "Junk") in fake_client.copy_mail_to_mailbox_calls
    assert ("INBOX", ["42", "43"], ['\\Deleted']) in fake_client.add_flags_calls


def test_perform_mail_batch_action_ham_success(monkeypatch):
    """Test batch-marking multiple mails as ham (not spam) in a single IMAP call."""
    module, fake_client = _make_module(monkeypatch)
    module.domain_mail_folder_name = {}

    batch_action_data = {"uids": [42, 43], "action": "ham"}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "Junk", batch_action_data)

    assert result["action"] == "ham"
    assert result["mail_uid"] == ["42", "43"]
    assert result["moved_to"] == "INBOX"
    assert ("Junk", ["42", "43"], "INBOX") in fake_client.copy_mail_to_mailbox_calls
    assert ("Junk", ["42", "43"], ['\\Deleted']) in fake_client.add_flags_calls


def test_perform_mail_batch_action_copy_success(monkeypatch):
    """Test batch-copying multiple mails to another folder in a single IMAP call."""
    module, fake_client = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "copy", "data": "Archive"}
    result = module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)

    assert result["action"] == "copy"
    assert result["mail_uid"] == ["42", "43"]
    assert result["from_folder"] == "INBOX"
    assert result["to_folder"] == "Archive"
    assert ("INBOX", ["42", "43"], "Archive") in fake_client.copy_mail_to_mailbox_calls
    # Copy should NOT delete the original mails
    assert ("INBOX", ["42", "43"], ['\\Deleted']) not in fake_client.add_flags_calls


def test_perform_mail_batch_action_copy_missing_destination(monkeypatch):
    """Test batch-copying without providing destination folder."""
    module, _ = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "copy"}
    with pytest.raises(RequestException, match="Missing or invalid destination folder for copy action"):
        module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)


def test_perform_mail_batch_action_invalid_action(monkeypatch):
    """Test handling of invalid batch action."""
    module, _ = _make_module(monkeypatch)

    batch_action_data = {"uids": [42, 43], "action": "invalid_action"}
    with pytest.raises(RequestException, match="Invalid action: invalid_action"):
        module.perform_mail_batch_action(ACCOUNT_ID, "INBOX", batch_action_data)


# ========== Tests for delete_mails error handling ==========

def test_delete_mails_with_preference_flag_deleted_only(monkeypatch):
    """Test delete_mails with FLAG_DELETED_ONLY preference."""
    module, fake_client = _make_module(monkeypatch)
    # Mock user preferences for FLAG_DELETED_ONLY behavior
    module.user.profile.preferences.get = lambda key, default: {
        "UserMailGeneralSettings": {"SOGO_U_MAIL_DELETE_BEHAVIOR": "FLAG_DELETED_ONLY"}
    }.get(key, default)

    module.delete_mails(ACCOUNT_ID, "INBOX", [1, 2, 3])
    # Should call with move_to_trash=False, permanently=False
    assert len(fake_client.delete_mails_by_uid_calls) == 1


def test_delete_mails_with_single_mail_uid(monkeypatch):
    """Test delete_mails with a single mail UID (as string)."""
    module, fake_client = _make_module(monkeypatch)

    module.delete_mails(ACCOUNT_ID, "INBOX", "42")
    assert len(fake_client.delete_mails_by_uid_calls) == 1


def test_delete_mails_with_client_error_on_delete_by_uid(monkeypatch):
    """Test delete_mails propagates client error."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Delete failed")

    fake_client.delete_mails_by_uid = raise_error

    with pytest.raises(RequestException, match="Delete failed"):
        module.delete_mails(ACCOUNT_ID, "INBOX", [1, 2, 3])


# ========== Tests for get_mail_detail error handling ==========

def test_get_mail_detail_with_error(monkeypatch):
    """Test get_mail_detail when client fails to fetch mail."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Mail not found")

    fake_client.fetch_mail = raise_error

    with pytest.raises(RequestException, match="Mail not found"):
        module.get_mail_detail(ACCOUNT_ID, "INBOX", "42")


# ========== Tests for get_mail_raw error handling ==========

def test_get_mail_raw_with_error(monkeypatch):
    """Test get_mail_raw when client fails to fetch raw content."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Mail not found")

    fake_client.fetch_mail_raw = raise_error

    with pytest.raises(RequestException, match="Mail not found"):
        module.get_mail_raw(ACCOUNT_ID, "INBOX", "42")


# ========== Tests for download_attachment ==========

def test_download_attachment_success(monkeypatch):
    """Test downloading an attachment successfully."""
    module, fake_client = _make_module(monkeypatch)
    attachment_data = b"test attachment data"
    content_type = "application/pdf"

    def fetch_attachment(folder_name, mail_uid, filename):
        return (attachment_data, content_type)

    fake_client.fetch_attachment = fetch_attachment

    result = module.download_attachment(ACCOUNT_ID, "INBOX", "42", "test.pdf")
    assert result == (attachment_data, content_type)


def test_download_attachment_not_found(monkeypatch):
    """Test downloading an attachment that doesn't exist."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Attachment not found")

    fake_client.fetch_attachment = raise_error

    with pytest.raises(RequestException, match="Attachment not found"):
        module.download_attachment(ACCOUNT_ID, "INBOX", "42", "nonexistent.pdf")


# ========== Tests for download_mail ==========

def test_download_mail_eml_format(monkeypatch):
    """Test downloading a mail in EML format."""
    module, fake_client = _make_module(monkeypatch)
    mail_content = 'Subject: Test\r\nFrom: sender@example.com\r\n\r\nBody'

    fake_client.fetch_mail_raw_result = mail_content

    result = module.download_mail(ACCOUNT_ID, "INBOX", "42", "eml")
    
    # Result should be BytesIO with the mail content
    assert isinstance(result, BytesIO)
    result.seek(0)
    assert result.read() == mail_content.encode()


def test_download_mail_zip_format(monkeypatch):
    """Test downloading a mail in ZIP format."""
    import zipfile
    from io import BytesIO
    
    module, fake_client = _make_module(monkeypatch)
    mail_content = 'Subject: Test\r\nFrom: sender@example.com\r\n\r\nBody'
    fake_client.fetch_mail_raw_result = mail_content

    result = module.download_mail(ACCOUNT_ID, "INBOX", "42", "zip")
    
    # Result should be BytesIO with zip content
    assert isinstance(result, BytesIO)
    result.seek(0)
    
    # Verify it's a valid zip
    with zipfile.ZipFile(result, 'r') as zf:
        files = zf.namelist()
        assert len(files) == 1
        assert files[0] == 'mail_42.eml'
        assert zf.read(files[0]) == mail_content.encode()


def test_download_mail_invalid_format(monkeypatch):
    """Test downloading a mail with invalid format defaults to eml."""
    module, fake_client = _make_module(monkeypatch)
    mail_content = 'Subject: Test\r\n\r\nBody'
    fake_client.fetch_mail_raw_result = mail_content

    result = module.download_mail(ACCOUNT_ID, "INBOX", "42", "invalid")
    
    # Should default to eml format
    assert isinstance(result, BytesIO)
    result.seek(0)
    assert result.read() == mail_content.encode()


# ========== Tests for delete_draft_mail ==========

def test_delete_draft_mail_success(monkeypatch):
    """Test deleting a draft mail successfully."""
    module, fake_client = _make_module(monkeypatch)
    
    def delete_draft(folder_type, uid):
        pass
    
    fake_client.delete_mail_permanently_from_folder_type = delete_draft

    # Should not raise
    module.delete_draft_mail(ACCOUNT_ID, "draft_123")


def test_delete_draft_mail_with_error(monkeypatch):
    """Test delete_draft_mail when client fails."""
    module, fake_client = _make_module(monkeypatch)

    def raise_error(*args, **kwargs):
        raise RequestException("Draft not found")

    fake_client.delete_mail_permanently_from_folder_type = raise_error

    with pytest.raises(RequestException, match="Draft not found"):
        module.delete_draft_mail(ACCOUNT_ID, "draft_123")


# ========== Tests for purge_all_folders ==========

def test_purge_all_folders_success(monkeypatch):
    """Test purging all folders in an account."""
    module, fake_client = _make_module(monkeypatch)
    
    # Set up folder list
    fake_client.list_folders_result = [
        {'name': 'INBOX', 'path': 'INBOX'},
        {'name': 'Sent', 'path': 'Sent'},
        {'name': 'Trash', 'path': 'Trash'}
    ]
    fake_client.purge_folder_result = 10  # 10 mails per folder

    purge_data = {"permanently_delete": False, "date": None}
    result = module.purge_all_folders(ACCOUNT_ID, purge_data)
    
    # Should have purged all 3 folders
    assert result['mails_deleted'] == 30


def test_purge_all_folders_empty_account(monkeypatch):
    """Test purging all folders when account has no folders."""
    module, fake_client = _make_module(monkeypatch)
    
    fake_client.list_folders_result = []
    fake_client.purge_folder_result = 0

    purge_data = {"permanently_delete": False, "date": None}
    result = module.purge_all_folders(ACCOUNT_ID, purge_data)
    
    assert result['mails_deleted'] == 0


def test_purge_all_folders_with_date_filter(monkeypatch):
    """Test purging all folders with date filter."""
    module, fake_client = _make_module(monkeypatch)
    
    fake_client.list_folders_result = [
        {'name': 'INBOX', 'path': 'INBOX'},
        {'name': 'Archive', 'path': 'Archive'}
    ]
    fake_client.purge_folder_result = 5

    purge_data = {"permanently_delete": False, "date": "2024-01-01"}
    result = module.purge_all_folders(ACCOUNT_ID, purge_data)
    
    assert result['mails_deleted'] == 10


def test_purge_all_folders_with_permanent_delete(monkeypatch):
    """Test purging all folders with permanent deletion."""
    module, fake_client = _make_module(monkeypatch)
    
    fake_client.list_folders_result = [
        {'name': 'INBOX', 'path': 'INBOX'},
        {'name': 'Sent', 'path': 'Sent'}
    ]
    fake_client.purge_folder_result = 15

    purge_data = {"permanently_delete": True, "date": None}
    result = module.purge_all_folders(ACCOUNT_ID, purge_data)
    
    assert result['mails_deleted'] == 30


# ========== Additional Tests for get_folder_mails with fields filtering ==========

def test_get_folder_mails_without_content_include_filter(monkeypatch):
    """Test getting mails without content using include filter."""
    module, fake_client = _make_module(monkeypatch)

    mail1 = _make_email_message(subject='Test1')

    def fetch_all_without_content(mailbox, number_of_mails, offset=0):
        yield {'nb_mails': 50}
        yield {'uid': '1', 'mail': mail1, 'flags': {'seen': True, 'flagged': False, 'answered': False, 'forwarded': False, 'deleted': False, 'all': ['\\Seen']}, 'size': 120}

    fake_client.fetch_all_mails_without_content = fetch_all_without_content

    # Mock collection param with fields that exclude content
    from unittest.mock import MagicMock
    collection_param = MagicMock()
    collection_param.first_item = 0
    collection_param.last_item = 9
    collection_param.fields = "uid,subject,from"
    collection_param.fields_action = "include"

    result, total = module.get_folder_mails(ACCOUNT_ID, "INBOX", collection_param)
    assert total == 50
    assert len(result) == 1
    assert 'contents' not in result[0]
    assert 'attachments' not in result[0]


def test_get_folder_mails_without_content_exclude_filter(monkeypatch):
    """Test getting mails without content using exclude filter."""
    module, fake_client = _make_module(monkeypatch)

    mail1 = _make_email_message(subject='Test1')

    def fetch_all_without_content(mailbox, number_of_mails, offset=0):
        yield {'nb_mails': 25}
        yield {'uid': '1', 'mail': mail1, 'flags': {'seen': False, 'flagged': False, 'answered': False, 'forwarded': False, 'deleted': False, 'all': []}, 'size': 120}

    fake_client.fetch_all_mails_without_content = fetch_all_without_content

    # Mock collection param with fields that exclude content
    from unittest.mock import MagicMock
    collection_param = MagicMock()
    collection_param.first_item = 0
    collection_param.last_item = 9
    collection_param.fields = "contents"
    collection_param.fields_action = "exclude"

    result, total = module.get_folder_mails(ACCOUNT_ID, "INBOX", collection_param)
    assert total == 25
    assert len(result) == 1
    assert 'contents' not in result[0]


# ========== Additional Tests for share_folder with removal ==========

def test_share_folder_with_user_removal(monkeypatch):
    """Test sharing a folder and removing a previously shared user."""
    module, fake_client = _make_module(monkeypatch)
    module.user.login_mail_server = 'owner@example.com'
    
    # Initial ACL with two users
    def get_acl_mock(folder_path):
        if fake_client.set_acl_calls:
            return [
                ('user1@example.com', {'userCanViewFolder': 1, 'userCanReadMails': 1}),
                ('user2@example.com', {'userCanViewFolder': 1})
            ]
        return [
            ('user1@example.com', {'userCanViewFolder': 1, 'userCanReadMails': 1}),
            ('user2@example.com', {'userCanViewFolder': 1})
        ]

    fake_client.get_acl = get_acl_mock

    # Only share with user1, removing user2
    share_data = [
        {
            "c_email": "user1@example.com",
            "rights": {"userCanViewFolder": 1, "userCanReadMails": 1}
        }
    ]

    result = list(module.share_folder(ACCOUNT_ID, "INBOX", share_data))
    
    # Should have called delete_acl for user2
    assert len(fake_client.delete_acl_calls) >= 1
    # Should have updated user1
    assert len(fake_client.set_acl_calls) >= 1


def test_share_folder_with_multiple_users(monkeypatch):
    """Test sharing a folder with multiple users."""
    module, fake_client = _make_module(monkeypatch)
    module.user.login_mail_server = 'owner@example.com'
    fake_client.get_acl_result = []

    def get_acl_after_share(folder_path):
        if fake_client.set_acl_calls:
            return [
                ('user1@example.com', {'userCanViewFolder': 1, 'userCanReadMails': 1}),
                ('user2@example.com', {'userCanViewFolder': 1})
            ]
        return []

    fake_client.get_acl = get_acl_after_share

    share_data = [
        {
            "c_email": "user1@example.com",
            "rights": {"userCanViewFolder": 1, "userCanReadMails": 1}
        },
        {
            "c_email": "user2@example.com",
            "rights": {"userCanViewFolder": 1}
        }
    ]

    result = list(module.share_folder(ACCOUNT_ID, "INBOX", share_data))
    
    # Should have called set_acl for both users
    assert len(fake_client.set_acl_calls) == 2
    identifiers = [call[1] for call in fake_client.set_acl_calls]
    assert 'user1@example.com' in identifiers
    assert 'user2@example.com' in identifiers
