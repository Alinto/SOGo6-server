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
        self.expunge_mailbox_args = None
        self.copy_mail_to_mailbox_args = None
        self.add_flags_to_mail_args = None
        self.expunge_mailbox_called = False
        self.copy_mail_to_mailbox_called = False
        self.add_flags_to_mail_called = False
        self.list_mailboxes_args = None
        self.create_folder_args = None
        self.delete_folder_args = None

        # --- Résultats configurables par test ---
        self.fetch_all_full_mails_result = []
        self.fetch_mail_result = b""
        self.mark_all_mails_in_folder_deleted_and_copy_to_trash_result = 0
        self.expunge_mailbox_result = None
        self.copy_mail_to_mailbox_result = None
        self.add_flags_to_mail_result = None
        self.list_mailboxes_result = []
        self.create_folder_result = None
        self.delete_folder_result = None

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

    def expunge_mailbox(self, folder_name):
        """
        Permanently remove all messages marked for deletion from the specified folder.
        """
        self.expunge_mailbox_args = folder_name
        self.expunge_mailbox_called = True

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

# --- expunge_mailbox ---

def test_given_valid_credentials_when_expunge_mailbox_then_success(monkeypatch):
    """
    Test the successful expunge of the mailbox.
    """
    # Given
    fake_client = FakeClientImap()
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.expunge_mailbox("user", "pwd", "INBOX")
    # Then
    assert ok is True
    assert msg == "OK"
    assert fake_client.logout_called
    assert fake_client.expunge_mailbox_called

def test_given_imap_error_when_expunge_mailbox_then_request_error(monkeypatch):
    """
    Test handling of IMAP errors during mailbox expunge.
    """
    # Given
    fake_client = FakeClientImap()
    def raise_expunge_mailbox(folder): raise RequestException("fail")
    fake_client.expunge_mailbox = raise_expunge_mailbox
    patch_import_and_instantiate_manager(monkeypatch, fake_client)
    module = ModuleMail(server="imap.example.org")
    # When
    ok, msg = module.expunge_mailbox("user", "pwd", "INBOX")
    # Then
    assert ok is False
    assert "fail" in msg
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
