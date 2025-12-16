"""
Tests unitaires pour InterfaceApiMailFolder (Interface layer).
Ces tests utilisent un fake ModuleMail pour tester la logique de l'interface.
"""
import pytest
from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.utils.exceptions import RequestException


class FakeModuleMail:
    """Fake ModuleMail for testing InterfaceApiMailFolder."""
    def __init__(self, user_conf=None):
        self.user_conf = user_conf
        # Track method calls
        self.get_folder_list_called = False
        self.create_folder_args = None
        self.delete_folder_args = None
        self.delete_all_mail_in_folder_args = None
        self.delete_mails_args = None
        self.move_mails_args = None
        self.expunge_folder_args = None
        self.update_folder_args = None
        self.get_folder_details_args = None
        self.purge_folder_mails_args = None
        self.get_folder_share_args = None
        self.share_folder_args = None

        # Configurable results
        self.get_folder_list_result = [{"name": "INBOX"}, {"name": "Sent"}]
        self.create_folder_result = {"name": "NewFolder"}
        self.delete_folder_result = {"folder_deleted": "Archive"}
        self.delete_all_mail_in_folder_result = None
        self.delete_mails_result = {"deleted_ids": [1, 2, 3]}
        self.move_mails_result = {"moved_ids": [1, 2]}
        self.expunge_folder_result = {"mail_deleted": 5}
        self.update_folder_result = {"name": "UpdatedFolder"}
        self.get_folder_details_result = {"name": "INBOX", "path": "INBOX"}
        self.purge_folder_mails_result = {"mails_deleted": 10}
        self.get_folder_share_result = {"users": {}}
        self.share_folder_result = {"users": {}}

    def get_folder_list(self):
        self.get_folder_list_called = True
        return self.get_folder_list_result

    def create_folder(self, folder_name):
        self.create_folder_args = folder_name
        return self.create_folder_result

    def delete_folder(self, folder_name):
        self.delete_folder_args = folder_name
        return self.delete_folder_result

    def delete_all_mail_in_folder(self, folder_name, before_date):
        self.delete_all_mail_in_folder_args = (folder_name, before_date)
        return self.delete_all_mail_in_folder_result

    def delete_mails(self, folder_name, mail_uids):
        self.delete_mails_args = (folder_name, mail_uids)
        return self.delete_mails_result

    def move_mails(self, from_folder, mail_uids, to_folder):
        self.move_mails_args = (from_folder, mail_uids, to_folder)
        return self.move_mails_result

    def expunge_folder(self, folder_name):
        self.expunge_folder_args = folder_name
        return self.expunge_folder_result

    def update_folder(self, folder_name, folder_data):
        self.update_folder_args = (folder_name, folder_data)
        return self.update_folder_result

    def get_folder_details(self, folder_name):
        self.get_folder_details_args = folder_name
        return self.get_folder_details_result

    def purge_folder_mails(self, folder_name, purge_data):
        self.purge_folder_mails_args = (folder_name, purge_data)
        return self.purge_folder_mails_result

    def get_folder_share(self, folder_name):
        self.get_folder_share_args = folder_name
        return self.get_folder_share_result

    def share_folder(self, folder_name, share_data):
        self.share_folder_args = (folder_name, share_data)
        return self.share_folder_result


def patch_module_on_interface(monkeypatch, fake_module):
    """Patch ModuleMail in InterfaceApiMailFolder module."""
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailFolder.ModuleMail",
        lambda user_conf=None: fake_module
    )


# ========== Tests for get_folder_list ==========

def test_get_folder_list_success(monkeypatch):
    """Test getting folder list for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_list(account_id=0)

    assert status_code == 200
    assert result["data"]["folders"] == [{"name": "INBOX"}, {"name": "Sent"}]
    assert fake_module.get_folder_list_called is True


def test_get_folder_list_invalid_account_id(monkeypatch):
    """Test error handling for invalid account ID."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_list(account_id=5)

    assert status_code >= 400
    # The error_msg comes from the error_msg dict, not the exception message
    assert result["error_code"] == 99999  # ERROR_UNKOWN
    assert result["error_msg"] == "Error has not been defined"


def test_get_folder_list_module_exception(monkeypatch):
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_list = lambda: (_ for _ in ()).throw(RequestException("Connection failed", 311))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_list(account_id=0)

    assert status_code >= 400
    assert result["error_code"] == 311  # ERROR_IMAP_CONNECTION_FAILED
    assert result["error_msg"] == "IMAP connection failed"


# ========== Tests for create_folder ==========

def test_create_folder_success(monkeypatch):
    """Test creating a folder for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.create_folder(account_id=0, folder_name="NewFolder")

    assert status_code == 201
    assert result["data"]["name"] == "NewFolder"
    assert fake_module.create_folder_args == "NewFolder"


def test_create_folder_module_error(monkeypatch):
    """Test error handling when folder creation fails."""
    fake_module = FakeModuleMail()
    fake_module.create_folder = lambda x: (_ for _ in ()).throw(RequestException("Folder exists", 400))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.create_folder(account_id=0, folder_name="Existing")

    assert status_code >= 400


# ========== Tests for delete_folder ==========

def test_delete_folder_success(monkeypatch):
    """Test deleting a folder for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_folder(account_id=0, folder_name="Archive")

    assert status_code == 204
    assert result == ""
    assert fake_module.delete_folder_args == "Archive"


def test_delete_folder_module_error(monkeypatch):
    """Test error handling when folder deletion fails."""
    fake_module = FakeModuleMail()
    fake_module.delete_folder = lambda x: (_ for _ in ()).throw(RequestException("Cannot delete", 400))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_folder(account_id=0, folder_name="Archive")

    assert status_code >= 400


# ========== Tests for delete_mails ==========

def test_delete_mails_success(monkeypatch):
    """Test deleting multiple mails for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_mails(account_id=0, folder_name="INBOX", mail_uids=[1, 2, 3])

    assert status_code == 200
    assert result["data"]["deleted_ids"] == [1, 2, 3]
    assert fake_module.delete_mails_args == ("INBOX", [1, 2, 3])


def test_delete_mails_module_error(monkeypatch):
    """Test error handling when mail deletion fails."""
    fake_module = FakeModuleMail()
    fake_module.delete_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot delete", 400))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_mails(account_id=0, folder_name="INBOX", mail_uids=[1, 2, 3])

    assert status_code >= 400


# ========== Tests for delete_all_mail_in_folder ==========

def test_delete_all_mail_in_folder_success(monkeypatch):
    """Test deleting all mails in a folder for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_all_mail_in_folder(account_id=0, folder_name="INBOX", before_date="2024-01-01")

    assert status_code == 204
    assert fake_module.delete_all_mail_in_folder_args == ("INBOX", "2024-01-01")


def test_delete_all_mail_in_folder_without_date(monkeypatch):
    """Test deleting all mails without date filter."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_all_mail_in_folder(account_id=0, folder_name="INBOX", before_date=None)

    assert status_code == 204
    assert fake_module.delete_all_mail_in_folder_args == ("INBOX", None)


# ========== Tests for move_mails ==========

def test_move_mails_success(monkeypatch):
    """Test moving multiple mails for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.move_mails_result = {"moved_ids": [11, 22]}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.move_mails(account_id=0, folder_name="INBOX", mail_uids=[11, 22], to_folder_name="Sent")

    assert status_code == 200
    assert result["data"]["moved_ids"] == [11, 22]
    assert fake_module.move_mails_args == ("INBOX", [11, 22], "Sent")


def test_move_mails_module_error(monkeypatch):
    """Test error handling when moving mails fails."""
    fake_module = FakeModuleMail()
    fake_module.move_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot move", 400))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.move_mails(account_id=0, folder_name="INBOX", mail_uids=[1, 2], to_folder_name="Trash")

    assert status_code >= 400


# ========== Tests for _get_user_conf ==========

def test_get_user_conf_no_config():
    """Test error when no user conf is provided."""
    interface = InterfaceApiMailFolder(user_conf=None)

    with pytest.raises(RequestException, match="No mailbox configuration available"):
        interface._get_user_conf(0)


def test_get_user_conf_missing_fields():
    """Test error when user conf is missing required fields."""
    user_conf = {"username": "test@example.com"}  # missing password and type
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    with pytest.raises(RequestException, match="Missing fields"):
        interface._get_user_conf(0)


def test_get_user_conf_unsupported_type():
    """Test error when user conf has unsupported type."""
    user_conf = {"username": "test@example.com", "password": "pass", "type": "pop3"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    with pytest.raises(RequestException, match="Unsupported mail type"):
        interface._get_user_conf(0)


def test_get_user_conf_list_config():
    """Test getting user conf from a list."""
    user_conf = [
        {"username": "test1@example.com", "password": "pass1", "type": "imap"},
        {"username": "test2@example.com", "password": "pass2", "type": "imap"}
    ]
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    conf = interface._get_user_conf(1)

    assert conf["username"] == "test2@example.com"


def test_get_user_conf_invalid_index():
    """Test error when account_id is out of range."""
    user_conf = [{"username": "test@example.com", "password": "pass", "type": "imap"}]
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    with pytest.raises(RequestException, match="Invalid account_id"):
        interface._get_user_conf(5)
