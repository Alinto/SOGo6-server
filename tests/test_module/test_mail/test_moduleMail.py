import pytest
from unittest import mock
from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException

# --- Fake ClientImap pour simuler les comportements ---
class FakeClientImap:
    """
    Fake ClientImap for testing purposes.
    """
    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.login_args = None
        self.logout_called = False
        self.fetch_all_full_mails_args = None
        self.fetch_mail_args = None
        self.mark_all_mails_in_folder_deleted_and_copy_to_trash_args = None
        self.expunge_folder_args = None
        self.copy_mail_to_mailbox_args = None
        self.add_flags_to_mail_args = None
        self.expunge_folder_called = False
        self.copy_mail_to_mailbox_called = False
        self.add_flags_to_mail_called = False
        self.list_mailboxes_args = None
        self.create_folder_args = None
        self.delete_folder_args = None

        # --- Résultats configurables par test ---
        self.fetch_all_full_mails_result = []
        self.fetch_mail_result = b""
        self.mark_all_mails_in_folder_deleted_and_copy_to_trash_result = 0
        self.expunge_folder_result = None
        self.copy_mail_to_mailbox_result = None
        self.add_flags_to_mail_result = None
        self.list_mailboxes_result = []
        self.create_folder_result = None
        self.delete_folder_result = None
        self.get_folder_details_result = {}
        self.rename_folder_args = None
        self.subscribe_folder_args = None
        self.unsubscribe_folder_args = None
        self.purge_folder_args = None
        self.purge_folder_called = False

    def login(self, username, password):
        """
        Login to the IMAP server.
        """
        self.login_args = (username, password)

    def logout(self):
        """
        Logout from the IMAP server.
        """
        self.logout_called = True

    def fetch_all_full_mails(self, folder_name):
        """
        Fetch all full emails from the specified folder.
        """
        self.fetch_all_full_mails_args = folder_name
        return self.fetch_all_full_mails_result

    def fetch_mail(self, folder_name, mail_id):
        """
        Fetch a specific email from the specified folder.
        """
        self.fetch_mail_args = (folder_name, mail_id)
        return self.fetch_mail_result

    def mark_all_mails_in_folder_deleted_and_copy_to_trash(self, folder, before_date):
        """
        Mark all emails in the specified folder as deleted and copy them to the trash.
        """
        self.mark_all_mails_in_folder_deleted_and_copy_to_trash_args = (folder, before_date)
        return self.mark_all_mails_in_folder_deleted_and_copy_to_trash_result

    def expunge_folder(self, folder_name):
        """
        Permanently remove all messages marked for deletion from the specified folder.
        """
        self.expunge_folder_args = folder_name
        self.expunge_folder_called = True

    def copy_mail_to_mailbox(self, mailbox, mail_id, dest_mailbox):
        """
        Copy a specific email to the specified mailbox.
        """
        self.copy_mail_to_mailbox_args = (mailbox, mail_id, dest_mailbox)
        self.copy_mail_to_mailbox_called = True

    def add_flags_to_mail(self, mailbox, mail_id, flags):
        """
        Add flags to a specific email in the specified mailbox.
        """
        self.add_flags_to_mail_args = (mailbox, mail_id, flags)
        self.add_flags_to_mail_called = True

    def get_folder_details(self, folder_name):
        """
        Get details of a specific folder.
        """
        return self.get_folder_details_result

    def rename_folder(self, old_name, new_name):
        """
        Rename a folder.
        """
        self.rename_folder_args = (old_name, new_name)

    def subscribe_folder(self, folder_name):
        """
        Subscribe to a folder.
        """
        self.subscribe_folder_args = folder_name

    def unsubscribe_folder(self, folder_name):
        """
        Unsubscribe from a folder.
        """
        self.unsubscribe_folder_args = folder_name

    def purge_folder(self, folder_name, before_date=None):
        """
        Mark all mails in a folder as deleted.
        """
        self.purge_folder_args = (folder_name, before_date)
        self.purge_folder_called = True

# --- Patch helper ---
def patch_import_and_instantiate_manager(monkeypatch, fake_client):
    """
    Patch the import and instantiation of the IMAP manager.
    """
    monkeypatch.setattr(
        "app.module.mail.ModuleMail.import_and_instantiate_manager",
        lambda module_path, module_and_class_name, module_args: fake_client
    )

# --- get_folder_mails ---

def test_given_valid_credentials_when_get_folder_mails_then_return_mail_list(monkeypatch):
    """
    Test the retrieval of emails from a specific folder.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.fetch_all_full_mails_result = [
        {"mail_bytes": b"Subject: Test\r\nFrom: John <john@example.com>\r\nTo: Jane <jane@example.com>\r\n\r\nbody", "flags": ["\\Seen"]},
        {"mail_bytes": b"Subject: Hello\r\nFrom: Alice <alice@example.com>\r\nTo: Bob <bob@example.com>\r\n\r\nanother body", "flags": []},
    ]
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    result = module.get_folder_mails("user", "pwd", "INBOX", page=1, per_page=20)
    # Then
    assert result["status"] is True
    assert len(result["mails"]) == 2
    assert result["errors"] is None
    assert result["mails"][0]["subject"] == "Test"
    assert result["mails"][1]["from_"]["name"] == "Alice"

def test_given_imap_error_when_get_folder_mails_then_error(monkeypatch):
    """
    Test handling of IMAP errors during email retrieval.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_fetch_all_full_mails(folder_name): raise RequestException("fail")
    fake_client.fetch_all_full_mails = raise_fetch_all_full_mails
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    result = module.get_folder_mails("user", "pwd", "INBOX")
    # Then
    assert result["status"] is False
    assert not result["mails"]
    assert "fail" in result["errors"]

# --- expunge_folder ---

def test_given_valid_credentials_when_expunge_folder_then_success(monkeypatch):
    """
    Test the successful expunge of the mailbox with mail count returned.
    """
    # Given
    fake_client = FakeClientImap()
    # Mock expunge_folder to return a count
    fake_client.expunge_folder = lambda folder_name: 5  # 5 mails deleted
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    
    # When
    result = module.expunge_folder(user_conf, "INBOX")
    
    # Then
    assert result == {"mail_deleted": 5}
    assert fake_client.logout_called


def test_given_no_deleted_mails_when_expunge_folder_then_zero_count(monkeypatch):
    """
    Test expunge when no mails were deleted (count is 0).
    """
    # Given
    fake_client = FakeClientImap()
    # Mock expunge_folder to return 0
    fake_client.expunge_folder = lambda folder_name: 0  # No mails deleted
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    
    # When
    result = module.expunge_folder(user_conf, "INBOX")
    
    # Then
    assert result == {"mail_deleted": 0}
    assert fake_client.logout_called


def test_given_imap_error_when_expunge_folder_then_request_error(monkeypatch):
    """
    Test handling of IMAP errors during mailbox expunge.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_expunge_folder(folder):
        raise RequestException("fail")
    fake_client.expunge_folder = raise_expunge_folder
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    
    # When/Then
    with pytest.raises(RequestException, match="fail"):
        module.expunge_folder(user_conf, "INBOX")
    
    assert fake_client.logout_called

# --- get_mail_detail ---

def test_given_valid_credentials_when_get_mail_detail_then_return_dict(monkeypatch):
    """
    Test the retrieval of a specific email's details.
    """
    # Given
    fake_client = FakeClientImap()
    # Un mail minimal RFC822 pour le parsing
    fake_client.fetch_mail_result = (
        b"Subject: UnitTest\r\nFrom: Me <me@example.com>\r\nTo: You <you@example.com>\r\n\r\nHello!"
    )
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    result = module.get_mail_detail("user", "pwd", "INBOX", "1")
    # Then
    assert result["status"] is True
    assert result["mail"]["subject"] == "UnitTest"
    assert "from_" in result["mail"]
    assert result["errors"] is None

def test_given_imap_error_when_get_mail_detail_then_error(monkeypatch):
    """
    Test handling of IMAP errors during specific email retrieval.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_fetch_mail(folder, mail_id): raise RequestException("fail")
    fake_client.fetch_mail = raise_fetch_mail
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    result = module.get_mail_detail("user", "pwd", "INBOX", "1")
    # Then
    assert result["status"] is False
    assert result["mail"] is None
    assert "fail" in result["errors"]

# --- delete_all_mail_in_folder ---

def test_given_valid_credentials_when_delete_all_mail_in_folder_then_success(monkeypatch):
    """
    Test the successful deletion of all emails in a folder.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.mark_all_mails_in_folder_deleted_and_copy_to_trash_result = 4
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.delete_all_mail_in_folder("user", "pwd", "INBOX", before_date="2024-01-01")
    # Then
    assert ok is True
    assert msg == "4 mails marked as deleted"
    assert fake_client.logout_called

def test_given_imap_error_when_delete_all_mail_in_folder_then_request_error(monkeypatch):
    """
    Test handling of IMAP errors during folder deletion.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_mark_all(folder, before): raise RequestException("fail")
    fake_client.mark_all_mails_in_folder_deleted_and_copy_to_trash = raise_mark_all
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.delete_all_mail_in_folder("user", "pwd", "INBOX", before_date=None)
    # Then
    assert ok is False
    assert "fail" in msg
    assert fake_client.logout_called

# --- delete_mail_by_id ---

def test_given_valid_credentials_when_delete_mail_by_id_then_success(monkeypatch):
    """
    Test the successful deletion of a specific email by ID.
    """
    # Given
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.delete_mail_by_id("user", "pwd", "INBOX", "2")
    # Then
    assert ok is True
    assert msg == "OK"
    assert fake_client.copy_mail_to_mailbox_called
    assert fake_client.add_flags_to_mail_called

def test_given_imap_error_when_delete_mail_by_id_then_request_error(monkeypatch):
    """
    Test handling of IMAP errors during specific email deletion.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_copy_mail(mailbox, mail_id, dest_mailbox): raise RequestException("fail")
    fake_client.copy_mail_to_mailbox = raise_copy_mail
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.delete_mail_by_id("user", "pwd", "INBOX", "2")
    # Then
    assert ok is False
    assert "fail" in msg

# --- move_mail ---

def test_given_valid_credentials_when_move_mail_then_success(monkeypatch):
    """
    Test the successful move of a specific email to another folder.
    """
    # Given
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.move_mail("user", "pwd", "INBOX", "3", "Sent")
    # Then
    assert ok is True
    assert msg == "OK"
    assert fake_client.copy_mail_to_mailbox_called
    assert fake_client.add_flags_to_mail_called
    # Vérifie les arguments
    assert fake_client.copy_mail_to_mailbox_args == ("INBOX", "3", "Sent")
    assert fake_client.add_flags_to_mail_args == ("INBOX", "3", ['\\Deleted'])

def test_given_imap_error_when_move_mail_then_request_error(monkeypatch):
    """
    Test handling of IMAP errors during specific email move.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_copy_mail(mailbox, mail_id, dest_mailbox): raise RequestException("fail")
    fake_client.copy_mail_to_mailbox = raise_copy_mail
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.move_mail("user", "pwd", "INBOX", "3", "Sent")
    # Then
    assert ok is False
    assert "fail" in msg



# --- get_folder_list ---

def test_given_valid_credentials_when_get_folder_list_then_return_folders(monkeypatch):
    """
    Test the retrieval of folders for a valid account.
    """
    # Given
    fake_client = FakeClientImap()
    # Simule deux mailboxes listées
    fake_client.list_mailboxes = lambda: [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Sent"']
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    result = module.get_folder_list("user", "pwd")
    # Then
    assert result["status"] is True
    assert {"name": "INBOX"} in result["folders"]
    assert {"name": "Sent"} in result["folders"]
    assert result["errors"] is None
    assert fake_client.logout_called

def test_given_imap_error_when_get_folder_list_then_error(monkeypatch):
    """
    Test handling of IMAP errors during folder list retrieval.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.list_mailboxes = lambda: (_ for _ in ()).throw(RequestException("fail"))
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    result = module.get_folder_list("user", "pwd")
    # Then
    assert result["status"] is False
    assert result["folders"] == []
    assert "fail" in result["errors"]
    assert fake_client.logout_called


# --- create_folder ---

def test_given_valid_credentials_when_create_folder_then_success(monkeypatch):
    """
    Test the successful creation of a mail folder.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.create_folder = lambda folder_name: None  # Simule succès
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.create_folder("user", "pwd", "Archive")
    # Then
    assert ok is True
    assert msg == "OK"
    assert fake_client.logout_called

def test_given_imap_error_when_create_folder_then_error(monkeypatch):
    """
    Test handling of IMAP errors during folder creation.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.create_folder = lambda folder_name: (_ for _ in ()).throw(RequestException("fail"))
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.create_folder("user", "pwd", "Archive")
    # Then
    assert ok is False
    assert "fail" in msg
    assert fake_client.logout_called


# --- delete_folder ---


def test_given_valid_credentials_when_delete_folder_then_success(monkeypatch):
    """
    Test the successful deletion of a mail folder.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.delete_folder = lambda folder_name: None  # Simule succès
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.delete_folder("user", "pwd", "Archive")
    # Then
    assert ok is True
    assert msg == "OK"
    assert fake_client.logout_called

def test_given_imap_error_when_delete_folder_then_error(monkeypatch):
    """
    Test handling of IMAP errors during folder deletion.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.delete_folder = lambda folder_name: (_ for _ in ()).throw(RequestException("fail"))
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.delete_folder("user", "pwd", "Archive")
    # Then
    assert ok is False
    assert "fail" in msg
    assert fake_client.logout_called


def test_given_valid_data_when_update_folder_rename_only_then_success(monkeypatch):
    """
    Test successful folder renaming.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "NewFolder_renamed",
        "path": "NewFolder_renamed",
        "sievePath": "NewFolder_renamed",
        "type": "folder",
        "flags": [],
        "subscribed": 0,
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap",
        "server": "imap.example.org",
        "port": 143
    }
    folder_data = {"name": "NewFolder_renamed"}
    
    # When
    result = module.update_folder(user_conf, "NewFolder", folder_data)
    
    # Then
    assert result["name"] == "NewFolder_renamed"
    assert fake_client.rename_folder_args == ("NewFolder", "NewFolder_renamed")
    assert fake_client.logout_called


def test_given_valid_data_when_update_folder_subscribe_only_then_success(monkeypatch):
    """
    Test successful folder subscription update.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "TestFolder",
        "path": "TestFolder",
        "sievePath": "TestFolder",
        "type": "folder",
        "flags": [],
        "subscribed": 1,
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap",
        "server": "imap.example.org",
        "port": 143
    }
    folder_data = {"subscribed": 1}
    
    # When
    result = module.update_folder(user_conf, "TestFolder", folder_data)
    
    # Then
    assert result["subscribed"] == 1
    assert fake_client.subscribe_folder_args == "TestFolder"
    assert fake_client.logout_called


def test_given_valid_data_when_update_folder_unsubscribe_then_success(monkeypatch):
    """
    Test successful folder unsubscription.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "TestFolder",
        "path": "TestFolder",
        "sievePath": "TestFolder",
        "type": "folder",
        "flags": [],
        "subscribed": 0,
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap",
        "server": "imap.example.org",
        "port": 143
    }
    folder_data = {"subscribed": 0}
    
    # When
    result = module.update_folder(user_conf, "TestFolder", folder_data)
    
    # Then
    assert result["subscribed"] == 0
    assert fake_client.unsubscribe_folder_args == "TestFolder"
    assert fake_client.logout_called


def test_given_valid_data_when_update_folder_complete_then_success(monkeypatch):
    """
    Test successful complete folder update (rename + subscribe + type).
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "NewFolder_complete",
        "path": "NewFolder_complete",
        "sievePath": "NewFolder_complete",
        "type": "folder",
        "flags": [],
        "subscribed": 1,
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap",
        "server": "imap.example.org",
        "port": 143
    }
    folder_data = {
        "name": "NewFolder_complete",
        "subscribed": 1,
        "type": "templates"
    }
    
    # When
    result = module.update_folder(user_conf, "OldFolder", folder_data)
    
    # Then
    assert result["name"] == "NewFolder_complete"
    assert result["type"] == "templates"  # Type is included in response
    assert fake_client.rename_folder_args == ("OldFolder", "NewFolder_complete")
    assert fake_client.subscribe_folder_args == "NewFolder_complete"
    assert fake_client.logout_called


def test_given_invalid_folder_name_when_update_folder_then_validation_error(monkeypatch):
    """
    Test validation error when folder_name is invalid.
    """
    # Given
    from marshmallow import ValidationError
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    folder_data = {"name": "NewName"}
    
    # When/Then
    with pytest.raises(ValidationError, match="folder_name is required"):
        module.update_folder(user_conf, "", folder_data)


def test_given_invalid_folder_data_when_update_folder_then_validation_error(monkeypatch):
    """
    Test validation error when folder_data is invalid.
    """
    # Given
    from marshmallow import ValidationError
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    
    # When/Then
    with pytest.raises(ValidationError, match="folder_data is required"):
        module.update_folder(user_conf, "TestFolder", None)


def test_given_valid_data_when_purge_folder_only_mark_deleted_then_success(monkeypatch):
    """
    Test purge folder without permanent deletion (only mark as deleted).
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "TestFolder",
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    purge_data = {
        "applyToSubfolders": False,
        "permanentlyDelete": False,
        "date": "2025-09-11"
    }
    
    # When
    module.purge_folder_mails(user_conf, "TestFolder", purge_data)
    
    # Then
    assert fake_client.purge_folder_called is True
    assert fake_client.purge_folder_args == ("TestFolder", "2025-09-11")
    assert fake_client.expunge_folder_called is False
    assert fake_client.logout_called is True


def test_given_valid_data_when_purge_folder_with_permanent_delete_then_success(monkeypatch):
    """
    Test purge folder with permanent deletion (mark as deleted + expunge).
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "TestFolder",
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    purge_data = {
        "applyToSubfolders": False,
        "permanentlyDelete": True,
        "date": "2025-09-11"
    }
    
    # When
    module.purge_folder_mails(user_conf, "TestFolder", purge_data)
    
    # Then
    assert fake_client.purge_folder_called is True
    assert fake_client.purge_folder_args == ("TestFolder", "2025-09-11")
    assert fake_client.expunge_folder_called is True
    assert fake_client.expunge_folder_args == "TestFolder"
    assert fake_client.logout_called is True


def test_given_apply_to_subfolders_when_purge_folder_then_all_folders_purged(monkeypatch):
    """
    Test purge folder with applyToSubfolders option.
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "ParentFolder",
        "children": [
            {
                "name": "SubFolder1",
                "path": "ParentFolder/SubFolder1",
                "children": []
            },
            {
                "name": "SubFolder2",
                "path": "ParentFolder/SubFolder2",
                "children": [
                    {
                        "name": "SubSubFolder",
                        "path": "ParentFolder/SubFolder2/SubSubFolder",
                        "children": []
                    }
                ]
            }
        ]
    }
    
    # Track all purge_folder calls
    purge_calls = []
    def mock_purge_folder(folder, before_date):
        purge_calls.append((folder, before_date))
    
    fake_client.purge_folder = mock_purge_folder
    
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    purge_data = {
        "applyToSubfolders": True,
        "permanentlyDelete": False,
        "date": "2025-09-11"
    }
    
    # When
    module.purge_folder_mails(user_conf, "ParentFolder", purge_data)
    
    # Then
    assert len(purge_calls) == 4  # Parent + 2 subfolders + 1 sub-subfolder
    assert ("ParentFolder", "2025-09-11") in purge_calls
    assert ("ParentFolder/SubFolder1", "2025-09-11") in purge_calls
    assert ("ParentFolder/SubFolder2", "2025-09-11") in purge_calls
    assert ("ParentFolder/SubFolder2/SubSubFolder", "2025-09-11") in purge_calls
    assert fake_client.logout_called is True


def test_given_no_date_when_purge_folder_then_all_mails_purged(monkeypatch):
    """
    Test purge folder without date filter (purge all mails).
    """
    # Given
    fake_client = FakeClientImap()
    fake_client.get_folder_details_result = {
        "name": "TestFolder",
        "children": []
    }
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    purge_data = {
        "applyToSubfolders": False,
        "permanentlyDelete": True
        # No date specified
    }
    
    # When
    module.purge_folder_mails(user_conf, "TestFolder", purge_data)
    
    # Then
    assert fake_client.purge_folder_called is True
    assert fake_client.purge_folder_args == ("TestFolder", None)
    assert fake_client.expunge_folder_called is True
    assert fake_client.logout_called is True


def test_given_invalid_folder_name_when_purge_folder_then_validation_error(monkeypatch):
    """
    Test validation error when folder_name is invalid for purge.
    """
    # Given
    from marshmallow import ValidationError
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    purge_data = {"permanentlyDelete": False}
    
    # When/Then
    with pytest.raises(ValidationError, match="folder_name is required"):
        module.purge_folder_mails(user_conf, "", purge_data)


def test_given_invalid_purge_data_when_purge_folder_then_validation_error(monkeypatch):
    """
    Test validation error when purge_data is invalid.
    """
    # Given
    from marshmallow import ValidationError
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    
    module = ModuleMail(server="imap.example.org")
    user_conf = {
        "username": "test@example.com",
        "password": "password123",
        "type": "imap"
    }
    
    # When/Then
    with pytest.raises(ValidationError, match="purge_data is required"):
        module.purge_folder_mails(user_conf, "TestFolder", None)
