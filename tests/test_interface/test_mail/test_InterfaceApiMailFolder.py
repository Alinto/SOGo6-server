"""
Tests unitaires pour InterfaceApiMailFolder (Interface layer).
Ces tests utilisent un fake ModuleMail pour tester la logique de l'interface.
"""
from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.utils.exceptions import RequestException
from app.utils import errors as err


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
        self.get_one_folder_args = None
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
        self.get_one_folder_result = {"name": "INBOX", "path": "INBOX"}
        self.purge_folder_mails_result = {"mails_deleted": 10}
        self.get_folder_share_result = {"users": {}}
        self.share_folder_result = {"users": {}}

    def get_folder_list(self):
        """Simulate getting folder list."""
        self.get_folder_list_called = True
        return self.get_folder_list_result

    def create_folder(self, folder_name):
        """Simulate creating a folder."""
        self.create_folder_args = folder_name
        return self.create_folder_result

    def delete_folder(self, folder_name):
        """Simulate deleting a folder."""
        self.delete_folder_args = folder_name
        return self.delete_folder_result

    def delete_all_mail_in_folder(self, folder_name, before_date):
        """Simulate deleting all mail in a folder."""
        self.delete_all_mail_in_folder_args = (folder_name, before_date)
        return self.delete_all_mail_in_folder_result

    def delete_mails(self, folder_name, mail_uids):
        """Simulate deleting specific mails in a folder."""
        self.delete_mails_args = (folder_name, mail_uids)
        return self.delete_mails_result

    def move_mails(self, from_folder, mail_uids, to_folder):
        """Simulate moving mails from one folder to another."""
        self.move_mails_args = (from_folder, mail_uids, to_folder)
        return self.move_mails_result

    def expunge_folder(self, folder_name):
        """Simulate expunging a folder."""
        self.expunge_folder_args = folder_name
        return self.expunge_folder_result

    def update_folder(self, folder_name, folder_data):
        """Simulate updating a folder."""
        self.update_folder_args = (folder_name, folder_data)
        return self.update_folder_result

    def get_one_folder(self, folder_name):
        """Simulate getting folder details."""
        self.get_one_folder_args = folder_name
        return self.get_one_folder_result

    def purge_folder_mails(self, folder_name, purge_data):
        """Simulate purging mails in a folder."""
        self.purge_folder_mails_args = (folder_name, purge_data)
        return self.purge_folder_mails_result

    def get_folder_share(self, folder_name):
        """Simulate getting folder share information."""
        self.get_folder_share_args = folder_name
        return self.get_folder_share_result

    def share_folder(self, folder_name, share_data):
        """Simulate sharing a folder."""
        self.share_folder_args = (folder_name, share_data)
        return self.share_folder_result

    def export_folder_mails(self, folder_name):
        """Simulate exporting mails from a folder."""
        self.export_folder_mails_args = folder_name
        return {"exported": True, "count": 42}


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
    assert result["data"] == [{"name": "INBOX"}, {"name": "Sent"}]
    assert fake_module.get_folder_list_called is True


def test_get_folder_list_invalid_account_id(monkeypatch):
    """Test error handling for invalid account ID."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_list(account_id=5)

    assert status_code >= 500
    # The error_msg comes from the error_msg dict, not the exception message
    assert result["error_code"] == "S999999"  # ERROR_UNKOWN
    assert result["error_msg"] == "Undefined Error"


def test_get_folder_list_module_exception(monkeypatch):
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_list = lambda: (_ for _ in ()).throw(RequestException("Connection failed", err.ERROR_IMAP_CONNECTION_FAILED))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_list(account_id=0)

    assert status_code >= 500
    assert result["error_code"] == "S000311"  # ERROR_IMAP_CONNECTION_FAILED
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
    fake_module.create_folder = lambda x: (_ for _ in ()).throw(RequestException("Folder exists", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.create_folder(account_id=0, folder_name="Existing")
    assert result["error_code"] == "S000300"
    assert status_code == 400


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
    fake_module.delete_folder = lambda x: (_ for _ in ()).throw(RequestException("Cannot delete", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_folder(account_id=0, folder_name="Archive")

    assert result["error_code"] == "S000300"
    assert status_code == 400


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
    fake_module.delete_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot delete", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_mails(account_id=0, folder_name="INBOX", mail_uids=[1, 2, 3])

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for delete_all_mail_in_folder ==========

def test_delete_all_mail_in_folder_success(monkeypatch):
    """Test deleting all mails in a folder for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_all_mail_in_folder(account_id=0, folder_name="INBOX", before_date="2024-01-01")

    assert result == ""
    assert status_code == 204
    assert fake_module.delete_all_mail_in_folder_args == ("INBOX", "2024-01-01")


def test_delete_all_mail_in_folder_without_date(monkeypatch):
    """Test deleting all mails without date filter."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.delete_all_mail_in_folder(account_id=0, folder_name="INBOX", before_date=None)

    assert result == ""
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
    fake_module.move_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot move", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.move_mails(account_id=0, folder_name="INBOX", mail_uids=[1, 2], to_folder_name="Trash")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for expunge_folder ==========

def test_expunge_folder_success(monkeypatch):
    """Test expunging a folder for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.expunge_folder_result = {"mail_deleted": 10}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.expunge_folder(account_id=0, folder_name="Trash")

    assert status_code == 200
    assert result["data"]["mail_deleted"] == 10
    assert fake_module.expunge_folder_args == "Trash"


def test_expunge_folder_module_error(monkeypatch):
    """Test error handling when folder expunge fails."""
    fake_module = FakeModuleMail()
    fake_module.expunge_folder = lambda x: (_ for _ in ()).throw(RequestException("Cannot expunge", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.expunge_folder(account_id=0, folder_name="Trash")

    assert status_code == 400
    assert result["error_code"] == "S000300"


# ========== Tests for update_folder ==========

def test_update_folder_success(monkeypatch):
    """Test updating a folder for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.update_folder_result = {"name": "RenamedFolder", "subscribed": True}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    folder_data = {"name": "RenamedFolder", "subscribed": True}
    result, status_code = interface.update_folder(account_id=0, folder_name="OldFolder", folder_data=folder_data)

    assert status_code == 200
    assert result["data"]["name"] == "RenamedFolder"
    assert fake_module.update_folder_args == ("OldFolder", folder_data)


def test_update_folder_module_error(monkeypatch):
    """Test error handling when folder update fails."""
    fake_module = FakeModuleMail()
    fake_module.update_folder = lambda *args: (_ for _ in ()).throw(RequestException("Cannot update", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.update_folder(account_id=0, folder_name="INBOX", folder_data={"name": "NewName"})

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for get_one_folder ==========

def test_get_one_folder_success(monkeypatch):
    """Test getting folder details for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.get_one_folder_result = {"name": "INBOX", "path": "INBOX", "message_count": 100}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_one_folder(account_id=0, folder_name="INBOX")

    assert status_code == 200
    assert result["data"]["name"] == "INBOX"
    assert result["data"]["message_count"] == 100
    assert fake_module.get_one_folder_args == "INBOX"


def test_get_one_folder_module_error(monkeypatch):
    """Test error handling when getting folder details fails."""
    fake_module = FakeModuleMail()
    fake_module.get_one_folder = lambda x: (_ for _ in ()).throw(RequestException("Folder not found", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_one_folder(account_id=0, folder_name="NonExistent")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for purge_folder_mails ==========

def test_purge_folder_mails_success(monkeypatch):
    """Test purging folder mails for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.purge_folder_mails_result = {"mails_deleted": 25}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    purge_data = {"permanently_delete": True, "date": "2024-01-01"}
    result, status_code = interface.purge_folder_mails(account_id=0, folder_name="Trash", purge_data=purge_data)

    assert status_code == 200
    assert result["data"]["mails_deleted"] == 25
    assert fake_module.purge_folder_mails_args == ("Trash", purge_data)


def test_purge_folder_mails_module_error(monkeypatch):
    """Test error handling when purging folder mails fails."""
    fake_module = FakeModuleMail()
    fake_module.purge_folder_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot purge", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.purge_folder_mails(account_id=0, folder_name="Trash", purge_data={})

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for export_folder_mails ==========

def test_export_folder_mails_success(monkeypatch):
    """Test exporting folder mails for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.export_folder_mails(account_id=0, folder_name="INBOX")

    assert status_code == 200
    assert result["data"]["exported"] is True
    assert result["data"]["count"] == 42
    assert fake_module.export_folder_mails_args == "INBOX"


def test_export_folder_mails_module_error(monkeypatch):
    """Test error handling when exporting folder mails fails."""
    fake_module = FakeModuleMail()
    fake_module.export_folder_mails = lambda x: (_ for _ in ()).throw(RequestException("Cannot export", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.export_folder_mails(account_id=0, folder_name="INBOX")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for get_folder_share ==========

def test_get_folder_share_success(monkeypatch):
    """Test getting folder share information for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share_result = {"users": {"user1@example.com": {"read": True, "write": False}}}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_share(account_id=0, folder_name="INBOX")

    assert status_code == 200
    assert "users" in result["data"]
    assert fake_module.get_folder_share_args == "INBOX"


def test_get_folder_share_module_error(monkeypatch):
    """Test error handling when getting folder share fails."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share = lambda x: (_ for _ in ()).throw(RequestException("Cannot get share", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.get_folder_share(account_id=0, folder_name="INBOX")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for share_folder ==========

def test_share_folder_success(monkeypatch):
    """Test sharing a folder for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.share_folder_result = {"users": {"user2@example.com": {"read": True, "write": True}}}
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    share_data = [{"email": "user2@example.com", "read": True, "write": True}]
    result, status_code = interface.share_folder(account_id=0, folder_name="INBOX", share_data=share_data)

    assert status_code == 200
    assert "users" in result["data"]
    assert fake_module.share_folder_args == ("INBOX", share_data)


def test_share_folder_module_error(monkeypatch):
    """Test error handling when sharing folder fails."""
    fake_module = FakeModuleMail()
    fake_module.share_folder = lambda *args: (_ for _ in ()).throw(RequestException("Cannot share", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailFolder(user_conf=user_conf)

    result, status_code = interface.share_folder(account_id=0, folder_name="INBOX", share_data=[])

    assert result["error_code"] == "S000300"
    assert status_code == 400
