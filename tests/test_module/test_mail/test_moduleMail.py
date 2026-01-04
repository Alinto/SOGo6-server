"""
Tests unitaires pour ModuleMail (Module layer).
Ces tests utilisent un fake ClientImap pour tester la logique métier du module.
"""
import pytest
from unittest import mock
import email
from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException


class FakeClientImap:
    """Fake ClientImap for testing ModuleMail."""
    def __init__(self, server='imap.example.com', port=143):
        self.server = server
        self.port = port
        self.logged_in = False
        self.selected_mailbox = None

        # Configurables results
        self.list_mailboxes_result = [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Sent"']
        self.create_folder_result = None
        self.delete_folder_result = None
        self.fetch_mails_result = ([], 0)
        self.fetch_mail_result = b'Subject: Test\r\nFrom: sender@example.com\r\nTo: recipient@example.com\r\n\r\nBody'
        self.expunge_folder_result = 5
        self.get_folder_details_result = {'name': 'INBOX', 'path': 'INBOX', 'type': 'inbox', 'subscribed': 1, 'children': []}
        self.get_acl_result = [('user1@example.com', {'userCanViewFolder': 1})]
        self.purge_folder_result = 10

        # Track method calls
        self.login_called = False
        self.logout_called = False
        self.select_mailbox_calls = []
        self.uid_copy_calls = []
        self.uid_store_flags_calls = []
        self.create_folder_calls = []
        self.delete_folder_calls = []
        self.rename_folder_calls = []
        self.subscribe_folder_calls = []
        self.unsubscribe_folder_calls = []
        self.set_acl_calls = []
        self.delete_acl_calls = []

    def login(self, username, password, auth_mech=None):
        self.logged_in = True
        self.login_called = True

    def logout(self):
        self.logged_in = False
        self.logout_called = True

    def select_mailbox(self, mailbox):
        self.selected_mailbox = mailbox
        self.select_mailbox_calls.append(mailbox)
        return 10  # Number of messages

    def list_mailboxes(self):
        return self.list_mailboxes_result

    def create_folder(self, folder_name):
        self.create_folder_calls.append(folder_name)
        if self.create_folder_result is not None:
            raise self.create_folder_result

    def delete_folder(self, folder_name):
        self.delete_folder_calls.append(folder_name)
        if self.delete_folder_result is not None:
            raise self.delete_folder_result

    def fetch_mails(self, mailbox, number_of_mails):
        return self.fetch_mails_result

    def fetch_mail(self, mailbox, mail_uid):
        return self.fetch_mail_result

    def fetch_mail_detail(self, mailbox, mail_uid):
        """Fetch mail with flags and size information."""
        return {
            'raw_message': self.fetch_mail_result,
            'flags': {
                'seen': False,
                'flagged': False,
                'answered': False,
                'forwarded': False,
                'all': []
            },
            'size': len(self.fetch_mail_result)
        }

    def uid_copy(self, mail_uid, dest_mailbox):
        self.uid_copy_calls.append((mail_uid, dest_mailbox))

    def uid_store_flags(self, mail_uid, flags, operation='+FLAGS'):
        self.uid_store_flags_calls.append((mail_uid, flags, operation))

    def expunge_folder(self, mailbox):
        return self.expunge_folder_result

    def get_folder_details(self, folder_name):
        return self.get_folder_details_result

    def rename_folder(self, old_name, new_name):
        self.rename_folder_calls.append((old_name, new_name))

    def subscribe_folder(self, folder_name):
        self.subscribe_folder_calls.append(folder_name)

    def unsubscribe_folder(self, folder_name):
        self.unsubscribe_folder_calls.append(folder_name)

    def get_acl(self, folder_name):
        return self.get_acl_result

    def set_acl(self, folder_name, identifier, rights):
        self.set_acl_calls.append((folder_name, identifier, rights))

    def delete_acl(self, folder_name, identifier):
        self.delete_acl_calls.append((folder_name, identifier))

    def purge_folder(self, mailbox, before_date=None):
        return self.purge_folder_result

    def get_mail_uids_before_date(self, mailbox, before_date=None, exclude_deleted=True):
        if before_date:
            return [1, 2, 3]
        return [1, 2, 3, 4, 5]

    def delete_mail_by_uid(self, mailbox, mail_uid):
        self.uid_copy_calls.append((mail_uid, 'Trash'))
        self.uid_store_flags_calls.append((mail_uid, ['\\Seen', '\\Deleted'], '+FLAGS'))

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


def patch_import_manager(monkeypatch, fake_client):
    """Patch import_and_instantiate_manager to return fake client."""
    monkeypatch.setattr(
        "app.module.mail.ModuleMail.import_and_instantiate_manager",
        lambda module_path, module_and_class_name, module_args: fake_client
    )


# ========== Tests for initialization ==========

def test_module_init_with_valid_user_conf(monkeypatch):
    """Test ModuleMail initialization with valid user conf."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {
        "username": "user@example.com",
        "password": "password",
        "type": "imap"
    }
    module = ModuleMail(user_conf=user_conf)

    assert module.client == fake_client
    assert fake_client.login_called is True


def test_module_init_without_user_conf():
    """Test ModuleMail initialization without user conf."""
    with pytest.raises(RequestException, match="user_conf is required"):
        ModuleMail(user_conf=None)


def test_module_init_with_missing_fields():
    """Test ModuleMail initialization with missing required fields."""
    user_conf = {"username": "user@example.com"}  # missing password
    with pytest.raises(RequestException, match="Missing required fields"):
        ModuleMail(user_conf=user_conf)


# ========== Tests for get_folder_list ==========

def test_get_folder_list_success(monkeypatch):
    """Test getting folder list."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.get_folder_list()
    assert len(result) == 2
    assert result[0]['name'] == 'INBOX'
    assert result[1]['name'] == 'Sent'


def test_get_folder_list_with_client_error(monkeypatch):
    """Test folder list retrieval with client error."""
    fake_client = FakeClientImap()
    fake_client.list_mailboxes = lambda: (_ for _ in ()).throw(RequestException("Connection failed"))
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    with pytest.raises(RequestException, match="Connection failed"):
        module.get_folder_list()


# ========== Tests for create_folder ==========

def test_create_folder_success(monkeypatch):
    """Test creating a folder."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.create_folder("NewFolder")
    assert result['name'] == "NewFolder"
    assert "NewFolder" in fake_client.create_folder_calls


def test_create_folder_with_client_error(monkeypatch):
    """Test folder creation with client error."""
    fake_client = FakeClientImap()
    fake_client.create_folder_result = RequestException("Folder already exists")
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    with pytest.raises(RequestException, match="Folder already exists"):
        module.create_folder("ExistingFolder")


# ========== Tests for delete_folder ==========

def test_delete_folder_not_in_trash_moves_to_trash(monkeypatch):
    """Test deleting a folder that is NOT in Trash - should move to Trash."""
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        'name': 'OldFolder',
        'path': 'OldFolder',
        'type': 'folder',
        'subscribed': 1,
        'children': []
    }
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.delete_folder("OldFolder")
    
    # Should move to Trash, not permanently delete
    assert result['folder_deleted'] == "OldFolder"
    assert result['permanently'] is False
    assert 'moved_to' in result
    assert result['moved_to'].startswith('Trash/')
    
    # Verify rename was called (move operation)
    assert len(fake_client.rename_folder_calls) == 1
    assert fake_client.rename_folder_calls[0][0] == "OldFolder"
    assert fake_client.rename_folder_calls[0][1].startswith("Trash/")
    
    # Verify delete was NOT called
    assert len(fake_client.delete_folder_calls) == 0


def test_delete_folder_in_trash_deletes_permanently(monkeypatch):
    """Test deleting a folder that IS in Trash - should permanently delete."""
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        'name': 'OldFolder_123',
        'path': 'Trash/OldFolder_123',
        'type': 'folder',
        'subscribed': 1,
        'children': []
    }
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.delete_folder("Trash/OldFolder_123")
    
    # Should permanently delete
    assert result['folder_deleted'] == "Trash/OldFolder_123"
    assert result['permanently'] is True
    
    # Verify delete was called
    assert "Trash/OldFolder_123" in fake_client.delete_folder_calls
    
    # Verify rename was NOT called
    assert len(fake_client.rename_folder_calls) == 0


def test_delete_trash_folder_itself(monkeypatch):
    """Test deleting the Trash folder itself - should permanently delete."""
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        'name': 'Trash',
        'path': 'Trash',
        'type': 'trash',
        'subscribed': 1,
        'children': []
    }
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.delete_folder("Trash")
    
    # Should permanently delete
    assert result['folder_deleted'] == "Trash"
    assert result['permanently'] is True
    
    # Verify delete was called
    assert "Trash" in fake_client.delete_folder_calls


# ========== Tests for get_folder_mails ==========

def test_get_folder_mails_success(monkeypatch):
    """Test getting mails from a folder."""
    fake_client = FakeClientImap()
    fake_client.fetch_mails_result = ([
        {
            'uid': 1,
            'mail_bytes': b'Subject: Test1\r\nFrom: sender1@example.com\r\nTo: recipient@example.com\r\nDate: Mon, 1 Jan 2024 10:00:00 +0000\r\n\r\nBody1',
            'flags': ['\\Seen']
        },
        {
            'uid': 2,
            'mail_bytes': b'Subject: Test2\r\nFrom: sender2@example.com\r\nTo: recipient@example.com\r\nDate: Mon, 2 Jan 2024 10:00:00 +0000\r\n\r\nBody2',
            'flags': []
        }
    ], 100)
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result, total = module.get_folder_mails("INBOX", first=0, last=10)
    assert total == 100
    assert len(result) == 2
    assert result[0]['subject'] == 'Test1'
    assert result[0]['seen'] is True
    assert result[1]['seen'] is False


def test_get_folder_mails_empty_folder(monkeypatch):
    """Test getting mails from empty folder."""
    fake_client = FakeClientImap()
    fake_client.fetch_mails_result = ([], 0)
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result, total = module.get_folder_mails("INBOX", first=0, last=10)
    assert total == 0
    assert len(result) == 0


# ========== Tests for delete_mails ==========

def test_delete_mails_success(monkeypatch):
    """Test deleting multiple mails."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.delete_mails("INBOX", [1, 2, 3])
    assert result['deleted_ids'] == [1, 2, 3]
    assert len(fake_client.uid_copy_calls) == 3


def test_delete_mails_partial_failure(monkeypatch):
    """Test deleting mails with partial failure."""
    fake_client = FakeClientImap()
    call_count = [0]

    def uid_copy_with_error(uid, dest):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RequestException("UID 2 not found")

    fake_client.uid_copy = uid_copy_with_error
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    with pytest.raises(RequestException, match="failed to be deleted"):
        module.delete_mails("INBOX", [1, 2, 3])


# ========== Tests for delete_all_mail_in_folder ==========

def test_delete_all_mail_in_folder_success(monkeypatch):
    """Test deleting all mails in a folder."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    module.delete_all_mail_in_folder("INBOX", before_date="2024-01-01")
    assert len(fake_client.uid_copy_calls) == 3  # get_mail_uids_before_date returns [1, 2, 3]


def test_delete_all_mail_in_folder_empty(monkeypatch):
    """Test deleting all mails when folder is empty."""
    fake_client = FakeClientImap()
    fake_client.get_mail_uids_before_date = lambda *args, **kwargs: []
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    module.delete_all_mail_in_folder("INBOX", before_date=None)
    assert len(fake_client.uid_copy_calls) == 0


# ========== Tests for expunge_folder ==========

def test_expunge_folder_success(monkeypatch):
    """Test expunging a folder."""
    fake_client = FakeClientImap()
    fake_client.expunge_folder_result = 5
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.expunge_folder("INBOX")
    assert result['mail_deleted'] == 5


# ========== Tests for move_mails ==========

def test_move_mails_success(monkeypatch):
    """Test moving mails to another folder."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.move_mails("INBOX", [1, 2, 3], "Archive")
    assert result['moved_ids'] == [1, 2, 3]
    assert len(fake_client.uid_copy_calls) == 3


# ========== Tests for get_mail_detail ==========

def test_get_mail_detail_success(monkeypatch):
    """Test getting mail details."""
    fake_client = FakeClientImap()
    fake_client.fetch_mail_result = b'Subject: Test\r\nFrom: sender@example.com\r\nTo: recipient@example.com\r\nDate: Mon, 1 Jan 2024 10:00:00 +0000\r\n\r\nBody content'
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.get_mail_detail("INBOX", 42)
    assert result['uid'] == "42"  # Now returns string
    assert result['subject'] == 'Test'
    assert result['content']['contentPlain'] == 'Body content'
    assert 'from' in result
    assert 'to' in result
    assert 'attachment' in result
    assert isinstance(result['attachment'], list)


# ========== Tests for delete_mail ==========

def test_delete_mail_success(monkeypatch):
    """Test deleting a single mail."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.delete_mail("INBOX", 42)
    assert result['uid_deleted'] == 42


# ========== Tests for get_mail_raw ==========

def test_get_mail_raw_success(monkeypatch):
    """Test getting raw mail content."""
    fake_client = FakeClientImap()
    fake_client.fetch_mail_result = b'Subject: Test\r\n\r\nBody'
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.get_mail_raw("INBOX", 42)
    assert result['raw'] == 'Subject: Test\r\n\r\nBody'


# ========== Tests for update_folder ==========

def test_update_folder_rename_success(monkeypatch):
    """Test updating folder with rename."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    folder_data = {"name": "NewName", "subscribed": 1}
    result = module.update_folder("OldName", folder_data)

    assert ("OldName", "NewName") in fake_client.rename_folder_calls
    assert "NewName" in fake_client.subscribe_folder_calls


def test_update_folder_subscribe_success(monkeypatch):
    """Test updating folder subscription status."""
    fake_client = FakeClientImap()
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    folder_data = {"subscribed": 0}
    module.update_folder("INBOX", folder_data)

    assert "INBOX" in fake_client.unsubscribe_folder_calls


# ========== Tests for get_folder_share ==========

def test_get_folder_share_success(monkeypatch):
    """Test getting folder share information."""
    fake_client = FakeClientImap()
    fake_client.get_acl_result = [
        ('user1@example.com', {'userCanViewFolder': 1, 'userCanReadMails': 1}),
        ('anyone', {'userCanViewFolder': 1})
    ]
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    result = module.get_folder_share("INBOX")
    assert 'users' in result
    assert 'user1@example.com' in result['users']
    assert 'anyone' in result['users']


# ========== Tests for share_folder ==========

def test_share_folder_success(monkeypatch):
    """Test sharing a folder with users."""
    fake_client = FakeClientImap()
    fake_client.get_acl_result = []
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "owner@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    share_data = [
        {
            "c_email": "user1@example.com",
            "rights": {"userCanViewFolder": 1, "userCanReadMails": 1}
        }
    ]

    result = module.share_folder("INBOX", share_data)
    assert len(fake_client.set_acl_calls) >= 1


# ========== Tests for purge_folder_mails ==========

def test_purge_folder_mails_success(monkeypatch):
    """Test purging folder mails."""
    fake_client = FakeClientImap()
    fake_client.purge_folder_result = 10
    fake_client.get_folder_details_result = {
        'name': 'INBOX',
        'children': []
    }
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    purge_data = {"applyToSubfolders": False, "permanentlyDelete": False}
    result = module.purge_folder_mails("INBOX", purge_data)

    assert result['mails_deleted'] == 10


def test_purge_folder_mails_with_subfolders(monkeypatch):
    """Test purging folder mails including subfolders."""
    fake_client = FakeClientImap()
    fake_client.purge_folder_result = 5
    fake_client.get_folder_details_result = {
        'name': 'INBOX',
        'children': [
            {'path': 'INBOX/Sub1'},
            {'path': 'INBOX/Sub2'}
        ]
    }

    def get_folder_details_dynamic(folder_name):
        if folder_name == 'INBOX':
            return {
                'name': 'INBOX',
                'children': [
                    {'path': 'INBOX/Sub1'},
                    {'path': 'INBOX/Sub2'}
                ]
            }
        return {'name': folder_name, 'children': []}

    fake_client.get_folder_details = get_folder_details_dynamic
    patch_import_manager(monkeypatch, fake_client)

    user_conf = {"username": "user@example.com", "password": "pass", "type": "imap"}
    module = ModuleMail(user_conf=user_conf)

    purge_data = {"applyToSubfolders": True, "permanentlyDelete": False}
    result = module.purge_folder_mails("INBOX", purge_data)

    # Should purge main folder + 2 subfolders = 15 mails total
    assert result['mails_deleted'] == 15
