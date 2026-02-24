"""
Tests unitaires pour InterfaceApiMailMailbox (Interface layer).
Ces tests utilisent un fake ModuleUserProfile pour tester la logique de l'interface.
"""
from app.interface.mail.InterfaceApiMailMailbox import InterfaceApiMailMailbox
from app.utils.exceptions import RequestException
from app.utils import errors as err


class FakeModuleUserProfile:
    """Fake ModuleUserProfile for testing InterfaceApiMailMailbox."""
    def __init__(self, process_setting=None, user_domain=None):
        self.process_setting = process_setting
        self.user_domain = user_domain

        # Memorisation des args pour vérification
        self.list_accounts_called = False
        self.create_external_account_args = None
        self.get_account_detail_args = None
        self.update_main_account_args = None
        self.update_external_account_args = None
        self.delete_external_account_args = None
        self.get_delegations_given_called = False
        self.add_delegation_given_args = None

        # Résultats configurables par test
        self.list_accounts_result = [
            {"id": "0", "email": "test@example.com", "type": "main"},
            {"id": "abc123", "email": "external@example.com", "type": "external"}
        ]
        self.create_external_account_result = {"id": "xyz789", "email": "new@example.com"}
        self.get_account_detail_result = {"id": "0", "email": "test@example.com", "server": "imap.example.com"}
        self.update_main_account_result = {"id": "0", "email": "test@example.com", "signature": "Updated"}
        self.update_external_account_result = {"id": "abc123", "email": "external@example.com", "updated": True}
        self.get_delegations_given_result = [{"email": "delegate1@example.com"}, {"email": "delegate2@example.com"}]
        self.add_delegation_given_result = {"email": "newdelegate@example.com", "added": True}

    def list_accounts(self, user):
        """List all accounts for a user."""
        self.list_accounts_called = True
        return self.list_accounts_result

    def create_external_account(self, user_uid, account_data):
        """Create an external account."""
        self.create_external_account_args = (user_uid, account_data)
        return self.create_external_account_result

    def get_account_detail(self, user, account_id):
        """Get account details."""
        self.get_account_detail_args = (user, account_id)
        return self.get_account_detail_result

    def update_main_account(self, user, account_data):
        """Update main account."""
        self.update_main_account_args = (user, account_data)
        return self.update_main_account_result

    def update_external_account(self, user, account_id, account_data):
        """Update external account."""
        self.update_external_account_args = (user, account_id, account_data)
        return self.update_external_account_result

    def delete_external_account(self, user, account_id):
        """Delete external account."""
        self.delete_external_account_args = (user, account_id)

    def get_delegations_given(self, user):
        """Get delegations given by user."""
        self.get_delegations_given_called = True
        return self.get_delegations_given_result

    def add_delegation_given(self, user, delegate_email):
        """Add a delegation."""
        self.add_delegation_given_args = (user, delegate_email)
        return self.add_delegation_given_result


class FakeUser:
    """Fake User for testing."""
    def __init__(self, uid="test_user"):
        self.uid = uid


class FakeProcessSetting:
    """Fake ProcessSetting for testing."""
    def __init__(self):
        pass


def patch_module_on_interface(monkeypatch, fake_module):
    """Patch ModuleUserProfile in InterfaceApiMailMailbox module."""
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleUserProfile",
        lambda process_setting, user_domain: fake_module
    )


def create_interface_with_settings(monkeypatch, fake_module, allow_external=True):
    """Helper to create interface with mocked settings."""
    patch_module_on_interface(monkeypatch, fake_module)

    # Mock UserModuleSettingsObj
    class FakeUserModuleSettings:
        """Fake UserModuleSettingsObj to control SOGO_D_ALLOW_EXT_MAIL_ACCOUNT setting."""
        def __init__(self, data):
            self.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT = allow_external

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.UserModuleSettingsObj",
        FakeUserModuleSettings
    )

    process_setting = FakeProcessSetting()
    user = FakeUser()
    user_domain = {"USER_MODULE_SETTINGS": {}}

    interface = InterfaceApiMailMailbox(
        process_setting=process_setting,
        user=user,
        user_domain=user_domain
    )

    return interface


# ========== Tests for list_mailboxes ==========

def test_list_mailboxes_success(monkeypatch):
    """Test listing all mailboxes for a user."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    result, status_code = interface.list_mailboxes()

    assert status_code == 200
    assert result["data"] == fake_module.list_accounts_result
    assert fake_module.list_accounts_called is True


def test_list_mailboxes_module_exception(monkeypatch):
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleUserProfile()
    fake_module.list_accounts = lambda user: (_ for _ in ()).throw(
        RequestException("Connection failed", err.ERROR_IMAP_CONNECTION_FAILED)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module)

    result, status_code = interface.list_mailboxes()

    assert status_code >= 500
    assert result["error_code"] == "S000311"


# ========== Tests for create_mailbox ==========

def test_create_mailbox_success(monkeypatch):
    """Test creating a new mailbox (external account)."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    account_data = {"email": "new@example.com", "password": "pass123"}
    result, status_code = interface.create_mailbox(account_data)

    assert status_code == 201
    assert result["data"]["id"] == "xyz789"
    assert fake_module.create_external_account_args[1] == account_data


def test_create_mailbox_external_forbidden(monkeypatch):
    """Test creating mailbox when external accounts are not allowed."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=False)

    account_data = {"email": "new@example.com", "password": "pass123"}
    _, status_code = interface.create_mailbox(account_data)

    assert status_code == 403


def test_create_mailbox_module_error(monkeypatch):
    """Test error handling when mailbox creation fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.create_external_account = lambda *args: (_ for _ in ()).throw(
        RequestException("Account exists", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    account_data = {"email": "existing@example.com", "password": "pass123"}
    _, status_code = interface.create_mailbox(account_data)

    assert status_code == 400


# ========== Tests for get_mailbox ==========

def test_get_mailbox_main_account_success(monkeypatch):
    """Test getting main account (account_id='0')."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    result, status_code = interface.get_mailbox(account_id="0")

    assert status_code == 200
    assert result["data"]["id"] == "0"
    assert fake_module.get_account_detail_args[1] == "0"


def test_get_mailbox_external_account_success(monkeypatch):
    """Test getting external account."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    _, status_code = interface.get_mailbox(account_id="abc123")

    assert status_code == 200
    assert fake_module.get_account_detail_args[1] == "abc123"


def test_get_mailbox_external_forbidden(monkeypatch):
    """Test getting external account when not allowed."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=False)

    result, status_code = interface.get_mailbox(account_id="abc123")

    assert status_code == 403
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_get_mailbox_module_error(monkeypatch):
    """Test error handling when getting mailbox fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.get_account_detail = lambda *args: (_ for _ in ()).throw(
        RequestException("Account not found", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module)

    _, status_code = interface.get_mailbox(account_id="0")

    assert status_code == 400


# ========== Tests for update_mailbox ==========

def test_update_mailbox_main_account_success(monkeypatch):
    """Test updating main account (account_id='0')."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    account_data = {"signature": "Updated signature"}
    result, status_code = interface.update_mailbox(account_id="0", account_data=account_data)

    assert status_code == 200
    assert result["data"]["signature"] == "Updated"
    assert fake_module.update_main_account_args[1] == account_data


def test_update_mailbox_external_account_success(monkeypatch):
    """Test updating external account."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    account_data = {"password": "newpass123"}
    result, status_code = interface.update_mailbox(account_id="abc123", account_data=account_data)

    assert status_code == 200
    assert result["data"]["updated"] is True
    assert fake_module.update_external_account_args[1] == "abc123"
    assert fake_module.update_external_account_args[2] == account_data


def test_update_mailbox_external_forbidden(monkeypatch):
    """Test updating external account when not allowed."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=False)

    account_data = {"password": "newpass123"}
    result, status_code = interface.update_mailbox(account_id="abc123", account_data=account_data)

    assert status_code == 403
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_update_mailbox_main_account_error(monkeypatch):
    """Test error handling when updating main account fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.update_main_account = lambda *args: (_ for _ in ()).throw(
        RequestException("Update failed", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module)

    _, status_code = interface.update_mailbox(account_id="0", account_data={})

    assert status_code == 400


def test_update_mailbox_external_account_error(monkeypatch):
    """Test error handling when updating external account fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.update_external_account = lambda *args: (_ for _ in ()).throw(
        RequestException("Update failed", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    _, status_code = interface.update_mailbox(account_id="abc123", account_data={})

    assert status_code == 400


# ========== Tests for delete_mailbox ==========

def test_delete_mailbox_success(monkeypatch):
    """Test deleting an external account."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    result, status_code = interface.delete_mailbox(account_id="abc123")

    assert status_code == 204
    assert result == ""
    assert fake_module.delete_external_account_args[1] == "abc123"


def test_delete_mailbox_main_account_forbidden(monkeypatch):
    """Test that deleting main account (account_id='0') is forbidden."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    result, status_code = interface.delete_mailbox(account_id="0")

    assert status_code == 403
    assert result["error_code"] == err.ERROR_MAIN_ACCOUNT_CANNOT_BE_DELETED.c


def test_delete_mailbox_external_forbidden(monkeypatch):
    """Test deleting external account when not allowed."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=False)

    result, status_code = interface.delete_mailbox(account_id="abc123")

    assert status_code == 403
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_delete_mailbox_module_error(monkeypatch):
    """Test error handling when mailbox deletion fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.delete_external_account = lambda *args: (_ for _ in ()).throw(
        RequestException("Cannot delete", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True)

    _, status_code = interface.delete_mailbox(account_id="abc123")

    assert status_code == 400


# ========== Tests for get_mailbox_delegates ==========

def test_get_mailbox_delegates_success(monkeypatch):
    """Test getting delegates for main account."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    result, status_code = interface.get_mailbox_delegates(account_id="0")

    assert status_code == 200
    assert len(result["data"]) == 2
    assert result["data"][0]["email"] == "delegate1@example.com"
    assert fake_module.get_delegations_given_called is True


def test_get_mailbox_delegates_external_forbidden(monkeypatch):
    """Test that getting delegates for external account is forbidden."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    result, status_code = interface.get_mailbox_delegates(account_id="abc123")

    assert status_code == 403
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_get_mailbox_delegates_module_error(monkeypatch):
    """Test error handling when getting delegates fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.get_delegations_given = lambda user: (_ for _ in ()).throw(
        RequestException("Cannot get delegates", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module)

    _, status_code = interface.get_mailbox_delegates(account_id="0")

    assert status_code == 400


# ========== Tests for create_mailbox_delegate ==========

def test_create_mailbox_delegate_success(monkeypatch):
    """Test creating a delegate for main account."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    data = {"email": "newdelegate@example.com"}
    result, status_code = interface.create_mailbox_delegate(account_id="0", data=data)

    assert status_code == 201
    assert result["data"]["email"] == "newdelegate@example.com"
    assert fake_module.add_delegation_given_args[1] == "newdelegate@example.com"


def test_create_mailbox_delegate_external_forbidden(monkeypatch):
    """Test that creating delegate for external account is forbidden."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module)

    data = {"email": "newdelegate@example.com"}
    result, status_code = interface.create_mailbox_delegate(account_id="abc123", data=data)
    print("__________________________")
    print(status_code, result)
    assert status_code == 403
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_create_mailbox_delegate_module_error(monkeypatch):
    """Test error handling when creating delegate fails."""
    fake_module = FakeModuleUserProfile()
    fake_module.add_delegation_given = lambda *args: (_ for _ in ()).throw(
        RequestException("Cannot add delegate", err.ERROR_VALIDATION_ERROR)
    )
    interface = create_interface_with_settings(monkeypatch, fake_module)

    data = {"email": "newdelegate@example.com"}
    _, status_code = interface.create_mailbox_delegate(account_id="0", data=data)

    assert status_code == 400
