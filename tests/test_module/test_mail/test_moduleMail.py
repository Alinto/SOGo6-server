"""
Tests unitaires pour ModuleMail (Module layer).
Ces tests utilisent un fake ClientMailServer pour tester la logique mtier du module.
"""
import pytest
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

    def expunge_folder(self, folder_path, do_subfolders=True):
        return self.expunge_folder_result

    def purge_folder(self, folder_path, before_date=None, do_subfolders=False, permanently_delete=False):
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
    mock_user.profile.preferences.get.return_value = {}
    mock_mail_settings = MagicMock()

    module = ModuleMail(user=mock_user, mail_settings=mock_mail_settings)
    # Patch _open_client_for to always return our fake client
    monkeypatch.setattr(module, '_open_client_for', lambda account_id, do_login=True: fake_client)
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


# ========== Tests for NotImplementedError methods ==========

def test_compose_email_not_implemented(monkeypatch):
    """Test that compose_email raises NotImplementedError."""
    module, _ = _make_module(monkeypatch)
    with pytest.raises(NotImplementedError, match="compose_email is not implemented yet"):
        module.compose_email()


def test_update_folder_not_implemented(monkeypatch):
    """Test that update_folder raises NotImplementedError."""
    module, _ = _make_module(monkeypatch)
    with pytest.raises(NotImplementedError):
        module.update_folder("INBOX", {"name": "NewName"})


def test_move_mails_not_implemented(monkeypatch):
    """Test that move_mails raises NotImplementedError."""
    module, _ = _make_module(monkeypatch)
    with pytest.raises(NotImplementedError):
        module.move_mails("INBOX", [1, 2, 3], "Archive")


def test_export_folder_mails_not_implemented(monkeypatch):
    """Test that export_folder_mails raises NotImplementedError."""
    module, _ = _make_module(monkeypatch)
    with pytest.raises(NotImplementedError, match="export_folder_mails is not implemented yet"):
        module.export_folder_mails("INBOX")


def test_reply_mail_not_implemented(monkeypatch):
    """Test that reply_mail raises NotImplementedError."""
    module, _ = _make_module(monkeypatch)
    with pytest.raises(NotImplementedError, match="reply_mail is not implemented yet"):
        module.reply_mail(ACCOUNT_ID, "INBOX", "42")


def test_forward_mail_not_implemented(monkeypatch):
    """Test that forward_mail raises NotImplementedError."""
    module, _ = _make_module(monkeypatch)
    with pytest.raises(NotImplementedError, match="forward_mail is not implemented yet"):
        module.forward_mail(ACCOUNT_ID, "INBOX", "42")


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
