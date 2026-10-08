"""
Tests unitaires pour InterfaceApiMailFolder (Interface layer).
Ces tests utilisent un fake ModuleMail pour tester la logique de l'interface.
"""
from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.factory.share.RepositoryAcl import AclEntry
from app.module.mail.ModuleMail import ModuleMail
from app.utils.exceptions import RequestException
from app.utils import constants as cs
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
        self.module_user_profile = FakeModuleUserProfile()
        self._user_source_module = FakeUserSourceModule()
        self._share_targets = {}


class FakeModuleUserProfile:
    """Fake ModuleUserProfile: records the user preferences updates."""
    def __init__(self):
        self.update_user_preferences_args = None

    def update_user_preferences(self, uid, new_data, subparent=None):
        """Simulate a partial update of the user preferences."""
        self.update_user_preferences_args = (uid, new_data, subparent)
        return new_data


class FakeUserSourceModule:
    """Fake ModuleUserSource: only the uids listed in known_uids are found in the user sources."""
    def __init__(self, known_uids=("bob@example.com",)):
        self.known_uids = set(known_uids)

    def get_contact_info_for_user(self, user_auth, user_to_find):
        """Simulate a user source hit by setting source_id, as the real module does."""
        if user_to_find.uid in self.known_uids:
            user_to_find.source_id = "fake_source"
            user_to_find.cn = user_to_find.uid


class FakeModuleMail:
    """Fake ModuleMail for testing InterfaceApiMailFolder.

    Method signatures match ModuleMail (most methods receive account_id as first argument).
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
        self.patch_folder_share_args = None
        self.put_folder_share_args = None
        self.post_folder_share_args = None
        self.export_folder_mails_args = None
        self.rename_folder_args = None
        self.prepare_folder_type_change_args = None

        # Configurable results
        self.get_folder_list_result = [{"name": "INBOX"}, {"name": "Sent"}]
        self.create_folder_result = {"name": "NewFolder"}
        self.move_mails_result = {"moved_ids": [1, 2]}
        self.expunge_folder_result = {"mail_deleted": 5}
        self.update_folder_result = {"name": "UpdatedFolder"}
        self.get_one_folder_result = {"name": "INBOX", "path": "INBOX"}
        self.purge_folder_mails_result = {"mails_deleted": 10}
        # Returns list of AclEntry, matching ModuleMail's DB+IMAP-backed ACL methods
        self.get_folder_share_result = []
        self.patch_folder_share_result = []
        self.put_folder_share_result = []
        self.post_folder_share_result = []
        self.rename_folder_result = {"name": "NewName", "path": "Parent/NewName", "type": cs.MAIL_FOLDER_NORMAL}
        self.prepare_folder_type_change_result = (
            {"name": "Archive", "path": "Archive", "type": cs.MAIL_FOLDER_JUNK},
            {"SOGO_U_JUNK_FOLDER_NAME": "Archive"},
        )

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
        """Simulate reading a folder's live ACL entries from IMAP."""
        self.get_folder_share_args = folder_path
        return self.get_folder_share_result

    def patch_folder_share(self, account_id, folder_path, users):
        """Simulate granting/updating a folder's ACL entries (IMAP + sogo6_acl), leaving others untouched."""
        self.patch_folder_share_args = (folder_path, users)
        return self.patch_folder_share_result

    def put_folder_share(self, account_id, folder_path, users):
        """Simulate replacing all of a folder's ACL entries (IMAP + sogo6_acl)."""
        self.put_folder_share_args = (folder_path, users)
        return self.put_folder_share_result

    def post_folder_share(self, account_id, folder_path, users):
        """Simulate granting a folder's ACL entries (IMAP + sogo6_acl), leaving others untouched."""
        self.post_folder_share_args = (folder_path, users)
        return self.post_folder_share_result

    def export_folder_mails(self, folder_name):
        """Simulate exporting mails from a folder."""
        self.export_folder_mails_args = folder_name
        return {"exported": True, "count": 42}

    def rename_folder(self, account_id, folder_path, new_name):
        """Simulate renaming a folder."""
        self.rename_folder_args = (account_id, folder_path, new_name)
        return self.rename_folder_result

    def prepare_folder_type_change(self, account_id, folder_path, folder_type):
        """Simulate checking a folder type change and building the user preferences patch."""
        self.prepare_folder_type_change_args = (account_id, folder_path, folder_type)
        return self.prepare_folder_type_change_result


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


# ========== Tests for folder share (GET/PATCH/PUT/POST) ==========
# ModuleMail is responsible for both the live IMAP ACL and its sogo6_acl (type "folder")
# mirror; the interface only resolves the request body then forwards to ModuleMail.

def test_get_folder_share_success(monkeypatch):
    """Test getting share info for a folder, including the 'anyone' pseudo entry."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share_result = [
        AclEntry(
            resource_type="folder", key="k", owner="owner@example.com", to_user="<default>",
            rights={"user_can_view_folder": 1, "user_can_read_mails": 1, "user_can_write_mails": 0},
        ),
    ]
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_share(account_id=0, folder_path="INBOX")

    assert status_code == 200
    assert fake_module.get_folder_share_args == "INBOX"
    users = result["data"]
    anyone = next(u for u in users if u["uid"] == "anyone")
    assert anyone["user_class"] == "anyone"
    assert anyone["rights"] == {"userCanViewFolder": 1, "userCanReadMails": 1}


def test_get_folder_share_module_error(monkeypatch):
    """Test error handling when reading the folder's live IMAP ACL fails."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share = lambda *args, **kwargs: (_ for _ in ()).throw(RequestException(error=err.ERROR_SHARE_NOT_FOUND))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_share(account_id=0, folder_path="INBOX")

    assert status_code == 404
    assert result["error_code"] == "S001100"


def test_patch_folder_share_success(monkeypatch):
    """Test that 'permissions' codes resolve to a full 11-flag rights dict, unlisted rights denied."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{"uid": "bob@example.com", "c_email": "bob@example.com", "user_class": "user", "permissions": ["l", "r"]}]
    result, status_code = interface.patch_folder_share(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 200
    folder_path, users = fake_module.patch_folder_share_args
    assert folder_path == "INBOX"
    assert users == [{
        "uid": "bob@example.com",
        "rights": {
            "user_can_view_folder": 1,
            "user_can_read_mails": 1,
            "user_can_mark_mails_read": 0,
            "user_can_write_mails": 0,
            "user_can_insert_mails": 0,
            "user_can_post_mails": 0,
            "user_can_create_subfolders": 0,
            "user_can_remove_folder": 0,
            "user_can_erase_mails": 0,
            "user_can_expunge_folder": 0,
            "user_is_administrator": 0,
        },
    }]


def test_patch_folder_share_anyone_user_class(monkeypatch):
    """Test that user_class 'anyone' resolves to the ANYONE_TO_USER pseudo-uid."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{"user_class": "anyone", "permissions": ["l", "r"]}]
    interface.patch_folder_share(account_id=0, folder_path="INBOX", share_data=share_data)

    _, users = fake_module.patch_folder_share_args
    assert users[0]["uid"] == "<default>"


def test_patch_folder_share_permissions_rights_mismatch(monkeypatch):
    """Test that conflicting 'permissions' and 'rights' fields return the mismatch error."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{
        "uid": "bob@example.com", "c_email": "bob@example.com", "user_class": "user",
        "permissions": ["l"], "rights": {"user_can_view_folder": 0},
    }]
    result, status_code = interface.patch_folder_share(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 400
    assert result["error_code"] == "S001103"


def test_patch_folder_share_module_error(monkeypatch):
    """Test error handling when the module rejects the share (e.g. sharing with oneself)."""
    fake_module = FakeModuleMail()
    fake_module.patch_folder_share = lambda *args, **kwargs: (_ for _ in ()).throw(RequestException(error=err.ERROR_SHARE_CANNOT_SHARE_WITH_SELF))
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.patch_folder_share(
        account_id=0, folder_path="INBOX",
        share_data=[{"uid": "bob@example.com", "c_email": "bob@example.com", "user_class": "user", "permissions": ["l"]}],
    )

    assert status_code == 400
    assert result["error_code"] == "S001102"


def test_put_folder_share_success(monkeypatch):
    """Test that PUT resolves rights and forwards them to put_folder_share."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{"uid": "bob@example.com", "c_email": "bob@example.com", "user_class": "user", "permissions": ["a"]}]
    result, status_code = interface.put_folder_share(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 200
    folder_path, users = fake_module.put_folder_share_args
    assert folder_path == "INBOX"
    assert users[0]["uid"] == "bob@example.com"
    assert users[0]["rights"]["user_is_administrator"] == 1


def test_post_folder_share_success(monkeypatch):
    """Test that POST resolves rights from the 'rights' field and forwards them to post_folder_share."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{
        "uid": "bob@example.com", "c_email": "bob@example.com", "user_class": "user",
        "rights": {"user_can_view_folder": 1, "user_can_read_mails": 1},
    }]
    result, status_code = interface.post_folder_share(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 200
    folder_path, users = fake_module.post_folder_share_args
    assert folder_path == "INBOX"
    assert users[0]["rights"]["user_can_view_folder"] == 1
    assert users[0]["rights"]["user_can_write_mails"] == 0


def test_get_folder_share_unknown_user_is_anonymous(monkeypatch):
    """Test that a to_user unknown to every user source is reported with user_class 'anonymous'."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_share_result = [
        AclEntry(resource_type="folder", key="k", owner="owner@example.com", to_user="bob@example.com",
                 rights={"user_can_view_folder": 1}),
        AclEntry(resource_type="folder", key="k", owner="owner@example.com", to_user="ghost@example.com",
                 rights={"user_can_view_folder": 1}),
    ]
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.get_folder_share(account_id=0, folder_path="INBOX")

    assert status_code == 200
    by_uid = {u["uid"]: u for u in result["data"]}
    assert by_uid["bob@example.com"]["user_class"] == "user"
    assert by_uid["ghost@example.com"]["user_class"] == "anonymous"


def test_post_folder_share_unknown_user_accepted_as_anonymous(monkeypatch):
    """Test that sharing with a uid unknown to the user sources is accepted and answered as 'anonymous'."""
    fake_module = FakeModuleMail()
    fake_module.post_folder_share_result = [
        AclEntry(resource_type="folder", key="k", owner="owner@example.com", to_user="ghost@example.com",
                 rights={"user_can_view_folder": 1}),
    ]
    interface = make_interface(monkeypatch, fake_module)

    share_data = [{"uid": "ghost@example.com", "c_email": "ghost@example.com", "user_class": "user", "permissions": ["l"]}]
    result, status_code = interface.post_folder_share(account_id=0, folder_path="INBOX", share_data=share_data)

    assert status_code == 200
    _, users = fake_module.post_folder_share_args
    assert users[0]["uid"] == "ghost@example.com"
    assert result["data"][0]["user_class"] == "anonymous"


# ========== Tests for folder_action (rename / type) ==========
# The interface only dispatches on the action and forwards to ModuleMail; a type change is
# then stored as a user preference through ModuleUserProfile.

def raise_request_exception(error):
    """Return a callable raising a RequestException with the given error, whatever its arguments."""
    def _raise(*args, **kwargs):
        raise RequestException(error=error)
    return _raise


def test_folder_action_rename_dispatches_to_rename_folder(monkeypatch):
    """Test that the 'rename' action calls ModuleMail.rename_folder and not the type change."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.folder_action("0", "Parent/Old", {"action": "rename", "data": "NewName"})

    assert status_code == 200
    assert result["data"] == fake_module.rename_folder_result
    assert fake_module.rename_folder_args == ("0", "Parent/Old", "NewName")
    assert fake_module.prepare_folder_type_change_args is None
    assert interface.module_user_profile.update_user_preferences_args is None


def test_folder_action_type_dispatches_to_change_folder_type(monkeypatch):
    """Test that the 'type' action calls the type change and not the rename."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.folder_action("0", "Archive", {"action": "type", "data": cs.MAIL_FOLDER_JUNK})

    assert status_code == 200
    assert result["data"]["type"] == cs.MAIL_FOLDER_JUNK
    assert fake_module.prepare_folder_type_change_args == ("0", "Archive", cs.MAIL_FOLDER_JUNK)
    assert fake_module.rename_folder_args is None


def test_rename_folder_module_error(monkeypatch):
    """Test that a module error on rename is returned as an API error."""
    fake_module = FakeModuleMail()
    fake_module.rename_folder = raise_request_exception(err.ERROR_FOLDER_ALREADY_EXIST)
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.rename_folder("0", "Old", "Existing")

    assert status_code == 409
    assert result["error_code"] == err.ERROR_FOLDER_ALREADY_EXIST.c
    assert result["data"] is None


def test_change_folder_type_updates_user_preferences(monkeypatch):
    """Test that a type change stores the module's patch in USER_MAIL_VIEW_SETTINGS for the user."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)
    interface.user.uid = "user@example.com"

    result, status_code = interface.change_folder_type("0", "Archive", cs.MAIL_FOLDER_JUNK)

    assert status_code == 200
    assert result["data"] == {"name": "Archive", "path": "Archive", "type": cs.MAIL_FOLDER_JUNK}
    assert interface.module_user_profile.update_user_preferences_args == (
        "user@example.com", {"SOGO_U_JUNK_FOLDER_NAME": "Archive"}, "USER_MAIL_VIEW_SETTINGS"
    )


def test_change_folder_type_module_error_does_not_update_preferences(monkeypatch):
    """Test that a refused type change returns the error and leaves the user preferences untouched."""
    fake_module = FakeModuleMail()
    fake_module.prepare_folder_type_change = raise_request_exception(err.ERROR_FOLDER_SPECIAL_CANNOT_CHANGE_TYPE)
    interface = make_interface(monkeypatch, fake_module)

    result, status_code = interface.change_folder_type("0", "Trash", cs.MAIL_FOLDER_JUNK)

    assert status_code == 400
    assert result["error_code"] == err.ERROR_FOLDER_SPECIAL_CANNOT_CHANGE_TYPE.c
    assert interface.module_user_profile.update_user_preferences_args is None


def test_change_folder_type_preferences_error(monkeypatch):
    """Test that an error while storing the user preferences is returned as an API error."""
    fake_module = FakeModuleMail()
    interface = make_interface(monkeypatch, fake_module)
    interface.module_user_profile.update_user_preferences = raise_request_exception(err.ERROR_USER_PROFILE_NOT_FOUND)

    result, status_code = interface.change_folder_type("0", "Archive", cs.MAIL_FOLDER_JUNK)

    assert result["error_code"] == err.ERROR_USER_PROFILE_NOT_FOUND.c
    assert status_code == err.ERROR_USER_PROFILE_NOT_FOUND.h


# ========== Tests for folder_action through the real ModuleMail ==========
# The real ModuleMail runs the business rules (ownership, special folders, main account only)
# against a fake mail client, so no IMAP server is needed.

class FakeMailClient:
    """Fake ClientMailServer holding a few folders, some of them shared with the user."""
    def __init__(self):
        self.folders = {
            "Parent/Old": {"name": "Old", "path": "Parent/Old", "delimiter": "/", "type": cs.MAIL_FOLDER_NORMAL},
            "Archive": {"name": "Archive", "path": "Archive", "delimiter": "/", "type": cs.MAIL_FOLDER_NORMAL},
            "Sent": {"name": "Sent", "path": "Sent", "delimiter": "/", "type": cs.MAIL_FOLDER_SENT},
            "Shared/bob/Projects": {"name": "Projects", "path": "Shared/bob/Projects", "delimiter": "/", "type": cs.MAIL_FOLDER_NORMAL},
        }
        self.rename_folder_args = None

    def get_one_folder(self, folder_path):
        """Return a copy of the folder, as the real client builds a new dict on each call."""
        if folder_path not in self.folders:
            raise RequestException(error=err.ERROR_FOLDER_NAME_NOT_FOUND)
        return dict(self.folders[folder_path])

    def is_folder_owned(self, folder_path):
        """Folders under the 'Shared/' namespace were shared with the user."""
        return not folder_path.startswith("Shared/")

    def rename_folder(self, old_name, new_name):
        """Rename the folder in place."""
        self.rename_folder_args = (old_name, new_name)
        folder = self.folders.pop(old_name)
        folder.update({"name": new_name.rsplit("/", 1)[-1], "path": new_name})
        self.folders[new_name] = folder


def make_interface_with_real_module(monkeypatch):
    """Create an interface using the real ModuleMail wired to a FakeMailClient."""
    client = FakeMailClient()
    module = ModuleMail(FakeUser(), mail_settings=None)
    monkeypatch.setattr(module, "_open_client_for", lambda account_id, do_login=True: client)
    interface = make_interface(monkeypatch, module)
    return interface, client


def test_action_rename_keeps_parent(monkeypatch):
    """Test that a rename only changes the last part of the path and returns the renamed folder."""
    interface, client = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Parent/Old", {"action": "rename", "data": "New"})

    assert status_code == 200
    assert client.rename_folder_args == ("Parent/Old", "Parent/New")
    assert result["data"]["path"] == "Parent/New"
    assert result["data"]["name"] == "New"


def test_action_rename_with_delimiter_refused(monkeypatch):
    """Test that a new name containing the folder delimiter is refused."""
    interface, client = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Parent/Old", {"action": "rename", "data": "a/b"})

    assert status_code == 400
    assert result["error_code"] == err.ERROR_FOLDER_DELIMITER.c
    assert client.rename_folder_args is None


def test_action_rename_special_folder_refused(monkeypatch):
    """Test that a special folder cannot be renamed."""
    interface, client = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Sent", {"action": "rename", "data": "MySent"})

    assert status_code == 400
    assert result["error_code"] == err.ERROR_FOLDER_SPECIAL_CANNOT_RENAME.c
    assert client.rename_folder_args is None


def test_action_rename_shared_folder_refused(monkeypatch):
    """Test that a folder shared with the user cannot be renamed, with the dedicated error."""
    interface, client = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Shared/bob/Projects", {"action": "rename", "data": "Mine"})

    assert status_code == 403
    assert result["error_code"] == err.ERROR_FOLDER_NOT_OWNER.c
    assert result["error_msg"] == err.ERROR_FOLDER_NOT_OWNER.m
    assert client.rename_folder_args is None


def test_action_rename_unknown_folder(monkeypatch):
    """Test that renaming a folder that does not exist returns not found."""
    interface, _ = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Nope", {"action": "rename", "data": "New"})

    assert status_code == 404
    assert result["error_code"] == err.ERROR_FOLDER_NAME_NOT_FOUND.c


def test_action_type_normal_to_special(monkeypatch):
    """Test that a normal folder can become special: only the user preference is updated."""
    interface, client = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Archive", {"action": "type", "data": cs.MAIL_FOLDER_JUNK})

    assert status_code == 200
    assert result["data"]["type"] == cs.MAIL_FOLDER_JUNK
    _, patch, subparent = interface.module_user_profile.update_user_preferences_args
    assert patch == {"SOGO_U_JUNK_FOLDER_NAME": "Archive"}
    assert subparent == "USER_MAIL_VIEW_SETTINGS"
    # The mail server itself is never modified by a type change
    assert client.rename_folder_args is None
    assert client.folders["Archive"]["type"] == cs.MAIL_FOLDER_NORMAL


def test_action_type_each_assignable_type_uses_its_preference(monkeypatch):
    """Test the preference written for every type the user can assign."""
    expected = {
        cs.MAIL_FOLDER_SENT: "SOGO_U_SENT_FOLDER_NAME",
        cs.MAIL_FOLDER_DRAFT: "SOGO_U_DRAFT_FOLDER_NAME",
        cs.MAIL_FOLDER_TRASH: "SOGO_U_TRASH_FOLDER_NAME",
        cs.MAIL_FOLDER_JUNK: "SOGO_U_JUNK_FOLDER_NAME",
        cs.MAIL_FOLDER_TEMPLATE: "SOGO_U_TEMPLATE_FOLDER_NAME",
    }
    for folder_type, pref_name in expected.items():
        interface, _ = make_interface_with_real_module(monkeypatch)

        _, status_code = interface.folder_action("0", "Archive", {"action": "type", "data": folder_type})

        assert status_code == 200
        assert interface.module_user_profile.update_user_preferences_args[1] == {pref_name: "Archive"}


def test_action_type_not_assignable_refused(monkeypatch):
    """Test that INBOX, PLANNED and NORMAL cannot be assigned by the user."""
    for folder_type in (cs.MAIL_FOLDER_INBOX, cs.MAIL_FOLDER_PLANNED, cs.MAIL_FOLDER_NORMAL):
        interface, _ = make_interface_with_real_module(monkeypatch)

        result, status_code = interface.folder_action("0", "Archive", {"action": "type", "data": folder_type})

        assert status_code == 400
        assert result["error_code"] == err.ERROR_FOLDER_TYPE_NOT_ASSIGNABLE.c
        assert interface.module_user_profile.update_user_preferences_args is None


def test_action_type_special_folder_refused(monkeypatch):
    """Test that the type of a special folder cannot be changed."""
    interface, _ = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Sent", {"action": "type", "data": cs.MAIL_FOLDER_JUNK})

    assert status_code == 400
    assert result["error_code"] == err.ERROR_FOLDER_SPECIAL_CANNOT_CHANGE_TYPE.c
    assert interface.module_user_profile.update_user_preferences_args is None


def test_action_type_shared_folder_refused(monkeypatch):
    """Test that the type of a folder shared with the user cannot be changed, with the dedicated error."""
    interface, _ = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("0", "Shared/bob/Projects", {"action": "type", "data": cs.MAIL_FOLDER_JUNK})

    assert status_code == 403
    assert result["error_code"] == err.ERROR_FOLDER_NOT_OWNER.c
    assert interface.module_user_profile.update_user_preferences_args is None


def test_action_type_external_account_refused(monkeypatch):
    """Test that folder types can only be changed on the main account (preferences are not per account)."""
    interface, _ = make_interface_with_real_module(monkeypatch)

    result, status_code = interface.folder_action("ext_hash", "Archive", {"action": "type", "data": cs.MAIL_FOLDER_JUNK})

    assert status_code == 400
    assert result["error_code"] == err.ERROR_FOLDER_TYPE_EXT_ACCOUNT.c
    assert interface.module_user_profile.update_user_preferences_args is None
