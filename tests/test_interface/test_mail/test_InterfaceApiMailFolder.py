"""
Tests unitaires pour InterfaceApiMailFolder (Interface layer).
Ces tests utilisent un fake ModuleMail pour tester la logique de l'interface.
"""
from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.utils.exceptions import RequestException
from app.utils import errors as err


# def InterfaceApiMailFolderWithInjectedConf(user_conf):
#     """
#     Crée une InterfaceApiMailFolder en contournant __init__ (qui requiert process_setting,
#     user_domain_settings et user), et injecte une implémentation simplifiée de _get_user_conf
#     basée sur un user_conf de type dict, list ou None.
#     """
#     REQUIRED_FIELDS = {"username", "password", "type"}

#     def _get_user_conf(self, account_id):
#         if self._user_conf is None:
#             raise RequestException("No mailbox configuration available", err.ERROR_UNKOWN)
#         if isinstance(self._user_conf, list):
#             try:
#                 conf = self._user_conf[int(account_id)]
#             except (IndexError, ValueError, TypeError) as exc:
#                 raise RequestException("Account not found", err.ERROR_UNKOWN) from exc
#         elif isinstance(self._user_conf, dict):
#             if int(account_id) != 0:
#                 raise RequestException("Account not found", err.ERROR_UNKOWN)
#             conf = self._user_conf
#         else:
#             raise RequestException("No mailbox configuration available", err.ERROR_UNKOWN)
#         missing = REQUIRED_FIELDS - conf.keys()
#         if missing:
#             raise RequestException(f"Missing fields: {missing}", err.ERROR_UNKOWN)
#         return conf

#     instance = object.__new__(InterfaceApiMailFolder)
#     instance._user_conf = user_conf  # noqa: SLF001
#     instance._get_user_conf = types.MethodType(_get_user_conf, instance)  # noqa: SLF001
#     return instance

class FakeUser:
    """Minimal fake User for testing, providing attributes accessed by the interface."""
    def __init__(self, login_mail_server="test@example.com"):
        self.login_mail_server = login_mail_server
        self.mail = login_mail_server
        self.cn = ""
        self.uid = ""
        self.anonymous = False


class InterfaceApiMailFolderWithInjectedConf(InterfaceApiMailFolder):
    """Subclass of InterfaceApiMailFolder that allows injecting user configuration directly for testing."""
    def __init__(self, user_conf, mail_module=None):
        """Initialize with injected user configuration for testing.
        
        Does not call the parent __init__ to avoid requiring process_setting,
        user_domain_settings and user. Sets mail_module directly if provided.
        """
        # Does not call the parent __init__ to avoid requiring all the parameters it needs
        self._user_conf = user_conf  # noqa: SLF001
        self.mail_module = mail_module
        self.user = FakeUser()
        self.user_domain_settings = {}


class FakeModuleMail:
    """Fake ModuleMail for testing InterfaceApiMailFolder.
    
    Method signatures match ModuleMail (most methods receive account_id as first argument).
    get_folder_share and share_folder return an iterator of (identifier, rights) tuples,
    matching ModuleMail's Iterator[tuple[str, dict[str, int]]] return type.
    """
    def __init__(self, user_conf=None):
        self.user_conf = user_conf
        # Track method calls
        self.get_folder_list_called = False
        self.create_folder_args = None
        self.delete_folder_args = None
        self.move_mails_args = None
        self.expunge_folder_args = None
        self.update_folder_args = None
        self.get_one_folder_args = None
        self.purge_folder_mails_args = None
        self.get_folder_share_args = None
        self.share_folder_args = None
        self.export_folder_mails_args = None

        # Configurable results
        self.get_folder_list_result = [{"name": "INBOX"}, {"name": "Sent"}]
        self.create_folder_result = {"name": "NewFolder"}
        self.move_mails_result = {"moved_ids": [1, 2]}
        self.expunge_folder_result = {"mail_deleted": 5}
        self.update_folder_result = {"name": "UpdatedFolder"}
        self.get_one_folder_result = {"name": "INBOX", "path": "INBOX"}
        self.purge_folder_mails_result = {"mails_deleted": 10}
        # Returns list of (identifier, rights) tuples (iterable, as ModuleMail yields them)
        self.get_folder_share_result = []
        self.share_folder_result = []

    def get_folder_list(self, account_id):
        """Simulate getting folder list."""
        self.get_folder_list_called = True
        return self.get_folder_list_result

    def create_folder(self, account_id, folder_name, parent_path=""):
        """Simulate creating a folder."""
        self.create_folder_args = folder_name
        return self.create_folder_result

    def delete_folder(self, account_id, folder_name, do_children=True):
        """Simulate deleting a folder."""
        self.delete_folder_args = folder_name

    def move_mails(self, from_folder, mail_uids, to_folder):
        """Simulate moving mails from one folder to another."""
        self.move_mails_args = (from_folder, mail_uids, to_folder)
        return self.move_mails_result

    def expunge_folder(self, account_id, folder_name, do_subfolders=True):
        """Simulate expunging a folder."""
        self.expunge_folder_args = folder_name
        return self.expunge_folder_result

    def update_folder(self, folder_name, folder_data):
        """Simulate updating a folder."""
        self.update_folder_args = (folder_name, folder_data)
        return self.update_folder_result

    def get_one_folder(self, account_id, folder_name):
        """Simulate getting folder details."""
        self.get_one_folder_args = folder_name
        return self.get_one_folder_result

    def purge_folder_mails(self, account_id, folder_name, purge_data):
        """Simulate purging mails in a folder."""
        self.purge_folder_mails_args = (folder_name, purge_data)
        return self.purge_folder_mails_result

    def get_folder_share(self, account_id, folder_path):
        """Simulate getting folder share information. Returns iterable of (identifier, rights) tuples."""
        self.get_folder_share_args = folder_path
        return iter(self.get_folder_share_result)

    def share_folder(self, account_id, folder_path, share_data):
        """Simulate sharing a folder. Returns iterable of (identifier, rights) tuples."""
        self.share_folder_args = (folder_path, share_data)
        return iter(self.share_folder_result)

    def export_folder_mails(self, folder_name):
        """Simulate exporting mails from a folder."""
        self.export_folder_mails_args = folder_name
        return {"exported": True, "count": 42}


def make_interface(monkeypatch, fake_module, user_conf=None):
    """Create an InterfaceApiMailFolderWithInjectedConf with the fake module injected."""
    if user_conf is None:
        user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailFolder.ModuleMail",
        lambda *args, **kwargs: fake_module
    )
    return InterfaceApiMailFolderWithInjectedConf(user_conf, mail_module=fake_module)


def patch_module_on_interface(monkeypatch, fake_module):
    """Patch ModuleMail in InterfaceApiMailFolder module."""
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailFolder.ModuleMail",
        lambda *args, **kwargs: fake_module
    )


# ========== Tests for get_folder_list ==========

def test_get_folder_list_success(monkeypatch):
    """Test getting folder list for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_list(account_id=0)

    assert status_code == 200
    assert result["data"] == [{"name": "INBOX"}, {"name": "Sent"}]
    assert fake_module.get_folder_list_called is True


def test_get_folder_list_module_exception(monkeypatch):
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_list = lambda account_id: (_ for _ in ()).throw(RequestException("Connection failed", err.ERROR_IMAP_CONNECTION_FAILED))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_list(account_id=0)

    assert status_code >= 500
    assert result["error_code"] == "S000311"  # ERROR_IMAP_CONNECTION_FAILED
    assert result["error_msg"] == "IMAP connection failed"


# ========== Tests for create_folder ==========

def test_create_folder_success(monkeypatch):
    """Test creating a folder for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.create_folder(account_id=0, folder_name="NewFolder")

    assert status_code == 201
    assert result["data"]["name"] == "NewFolder"
    assert fake_module.create_folder_args == "NewFolder"


def test_create_folder_module_error(monkeypatch):
    """Test error handling when folder creation fails."""
    fake_module = FakeModuleMail()
    fake_module.create_folder = lambda *args, **kwargs: (_ for _ in ()).throw(RequestException("Folder exists", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.create_folder(account_id=0, folder_name="Existing")
    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for delete_folder ==========

def test_delete_folder_success(monkeypatch):
    """Test deleting a folder for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.delete_folder(account_id=0, folder_name="Archive")

    assert status_code == 204
    assert result == ""
    assert fake_module.delete_folder_args == "Archive"


def test_delete_folder_module_error(monkeypatch):
    """Test error handling when folder deletion fails."""
    fake_module = FakeModuleMail()
    fake_module.delete_folder = lambda *args, **kwargs: (_ for _ in ()).throw(RequestException("Cannot delete", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.delete_folder(account_id=0, folder_name="Archive")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for expunge_folder ==========

def test_expunge_folder_success(monkeypatch):
    """Test expunging a folder for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.expunge_folder_result = {"mail_deleted": 10}
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.expunge_folder(account_id=0, folder_name="Trash", expunge_data={"do_subfolders": False})

    assert status_code == 200
    assert result["data"]["mail_deleted"] == 10
    assert fake_module.expunge_folder_args == "Trash"


def test_expunge_folder_module_error(monkeypatch):
    """Test error handling when folder expunge fails."""
    fake_module = FakeModuleMail()
    fake_module.expunge_folder = lambda *args, **kwargs: (_ for _ in ()).throw(RequestException("Cannot expunge", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.expunge_folder(account_id=0, folder_name="Trash", expunge_data={"do_subfolders": False})

    assert status_code == 400
    assert result["error_code"] == "S000300"


# ========== Tests for update_folder ==========

def test_update_folder_success(monkeypatch):
    """Test updating a folder for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.update_folder_result = {"name": "RenamedFolder", "subscribed": True}
    interface = make_interface(monkeypatch, fake_module)

    folder_data = {"name": "RenamedFolder", "subscribed": True}
    result, status_code = interface.update_folder(account_id=0, folder_name="OldFolder", folder_data=folder_data)

    assert status_code == 200
    assert result["data"]["name"] == "RenamedFolder"
    assert fake_module.update_folder_args == ("OldFolder", folder_data)


def test_update_folder_module_error(monkeypatch):
    """Test error handling when folder update fails."""
    fake_module = FakeModuleMail()
    fake_module.update_folder = lambda *args: (_ for _ in ()).throw(RequestException("Cannot update", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.update_folder(account_id=0, folder_name="INBOX", folder_data={"name": "NewName"})

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for get_one_folder ==========

def test_get_one_folder_success(monkeypatch):
    """Test getting folder details for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.get_one_folder_result = {"name": "INBOX", "path": "INBOX", "message_count": 100}
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_one_folder(account_id=0, folder_name="INBOX")

    assert status_code == 200
    assert result["data"]["name"] == "INBOX"
    assert result["data"]["message_count"] == 100
    assert fake_module.get_one_folder_args == "INBOX"


def test_get_one_folder_module_error(monkeypatch):
    """Test error handling when getting folder details fails."""
    fake_module = FakeModuleMail()
    fake_module.get_one_folder = lambda *args: (_ for _ in ()).throw(RequestException("Folder not found", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_one_folder(account_id=0, folder_name="NonExistent")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for purge_folder_mails ==========

def test_purge_folder_mails_success(monkeypatch):
    """Test purging folder mails for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.purge_folder_mails_result = {"mails_deleted": 25}
    interface = make_interface(monkeypatch, fake_module)

    purge_data = {"permanently_delete": True, "date": "2024-01-01"}
    result, status_code = interface.purge_folder_mails(account_id=0, folder_name="Trash", purge_data=purge_data)

    assert status_code == 200
    assert result["data"]["mails_deleted"] == 25
    assert fake_module.purge_folder_mails_args == ("Trash", purge_data)


def test_purge_folder_mails_module_error(monkeypatch):
    """Test error handling when purging folder mails fails."""
    fake_module = FakeModuleMail()
    fake_module.purge_folder_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot purge", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.purge_folder_mails(account_id=0, folder_name="Trash", purge_data={})

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for export_folder_mails ==========

def test_export_folder_mails_success(monkeypatch):
    """Test exporting folder mails for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.export_folder_mails(account_id=0, folder_name="INBOX")

    assert status_code == 200
    assert result["data"]["exported"] is True
    assert result["data"]["count"] == 42
    assert fake_module.export_folder_mails_args == "INBOX"


def test_export_folder_mails_module_error(monkeypatch):
    """Test error handling when exporting folder mails fails."""
    fake_module = FakeModuleMail()
    fake_module.export_folder_mails = lambda x: (_ for _ in ()).throw(RequestException("Cannot export", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.export_folder_mails(account_id=0, folder_name="INBOX")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for get_folder_share ==========

def test_get_folder_share_success(monkeypatch):
    """Test getting folder share information for a valid account (empty share list)."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share_result = []  # No shares: yields nothing
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_share(account_id=0, folder_path="INBOX")

    assert status_code == 200
    assert result["data"] == {}
    assert fake_module.get_folder_share_args == "INBOX"


def test_get_folder_share_with_users(monkeypatch):
    """Test getting folder share with existing users returns an 'anyone' entry."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share_result = [
        ("anyone", {"read": 1, "write": 0}),
    ]
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_share(account_id=0, folder_path="INBOX")

    assert status_code == 200
    assert "anyone" in result["data"]
    assert result["data"]["anyone"]["rights"] == {"read": 1, "write": 0}


def test_get_folder_share_module_error(monkeypatch):
    """Test error handling when getting folder share fails."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share = lambda *args: (_ for _ in ()).throw(RequestException("Cannot get share", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_share(account_id=0, folder_path="INBOX")

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for share_folder ==========

def test_share_folder_success(monkeypatch):
    """Test sharing a folder for a valid account (empty result)."""
    fake_module = FakeModuleMail()
    fake_module.share_folder_result = []  # No shares returned after update
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{"email": "user2@example.com", "read": True, "write": True}]
    result, status_code = interface.share_folder(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 200
    assert result["data"] == {}
    assert fake_module.share_folder_args == ("INBOX", share_data)


def test_share_folder_with_anyone(monkeypatch):
    """Test sharing a folder returns an 'anyone' ACL entry."""
    fake_module = FakeModuleMail()
    fake_module.share_folder_result = [
        ("anyone", {"read": 1, "write": 1}),
    ]
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{"email": "anyone", "read": True, "write": True}]
    result, status_code = interface.share_folder(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 200
    assert "anyone" in result["data"]
    assert result["data"]["anyone"]["rights"] == {"read": 1, "write": 1}


def test_share_folder_module_error(monkeypatch):
    """Test error handling when sharing folder fails."""
    fake_module = FakeModuleMail()
    fake_module.share_folder = lambda *args: (_ for _ in ()).throw(RequestException("Cannot share", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.share_folder(account_id=0, folder_path="INBOX", share_data=[])

    assert result["error_code"] == "S000300"
    assert status_code == 400
