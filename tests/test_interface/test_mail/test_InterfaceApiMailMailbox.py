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


def create_interface_with_settings(monkeypatch, fake_module, allow_external=True, fake_mail_module_class=None):
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

    # Mock MailSettingsObj
    class FakeMailSettings:
        """Fake MailSettingsObj for testing."""
        def __init__(self, data):
            pass

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.MailSettingsObj",
        FakeMailSettings
    )

    # Mock ModuleMail
    if fake_mail_module_class is None:
        class FakeModuleMail:
            """Fake ModuleMail for testing."""
            def __init__(self, user, mail_settings, process_setting=None):
                pass

            def get_mailbox_quota(self, account_id):
                return None
        fake_mail_module_class = FakeModuleMail

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMail",
        fake_mail_module_class
    )

    process_setting = FakeProcessSetting()
    user = FakeUser()
    user_domain = {"USER_MODULE_SETTINGS": {}, "MAIL_SETTINGS": {}}

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


# ========== Tests for purge_mailbox ==========

def test_purge_mailbox_success(monkeypatch):
    """Test purging all folders in a mailbox."""
    # Create a proper fake module
    class FakeModuleMailForPurge:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def purge_all_folders(self, account_id, purge_data):
            return {"mails_deleted": 150, "folders_processed": 8}
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForPurge)
    
    purge_data = {"permanently_delete": True, "date": "2024-01-01"}
    result, status_code = interface.purge_mailbox(account_id="0", purge_data=purge_data)

    assert status_code == 200
    assert result["data"]["mails_deleted"] == 150


def test_purge_mailbox_external_account_success(monkeypatch):
    """Test purging external account mailbox."""
    class FakeModuleMailForPurge:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def purge_all_folders(self, account_id, purge_data):
            return {"mails_deleted": 50}
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True, fake_mail_module_class=FakeModuleMailForPurge)
    
    result, status_code = interface.purge_mailbox(account_id="abc123", purge_data={})

    assert status_code == 200


def test_purge_mailbox_external_forbidden(monkeypatch):
    """Test purging external account when not allowed."""
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=False)
    
    result, status_code = interface.purge_mailbox(account_id="abc123", purge_data={})

    assert status_code == 403
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_purge_mailbox_module_error(monkeypatch):
    """Test error handling when purge fails."""
    class FakeModuleMailForPurge:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def purge_all_folders(self, account_id, purge_data):
            raise RequestException("Purge failed", err.ERROR_VALIDATION_ERROR)
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForPurge)
    
    result, status_code = interface.purge_mailbox(account_id="0", purge_data={})

    assert status_code == 400


# ========== Tests for save_draft ==========

def test_save_draft_new_success(monkeypatch):
    """Test creating a new draft."""
    class FakeModuleMailForDraft:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_draft(self, account_id, mail_data, key):
            return {"draft_key": "draft_456", "saved": True}
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForDraft)
    
    mail_data = {"to": "recipient@example.com", "subject": "Draft", "body": "Draft body"}
    result, status_code = interface.save_draft(account_id="0", mail_data=mail_data, key=None)

    assert status_code == 200
    assert result["data"]["draft_key"] == "draft_456"


def test_save_draft_update_existing(monkeypatch):
    """Test updating an existing draft."""
    class FakeModuleMailForDraft:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_draft(self, account_id, mail_data, key):
            return {"draft_key": key, "updated": True}
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForDraft)
    
    mail_data = {"to": "recipient@example.com", "subject": "Updated Draft"}
    result, status_code = interface.save_draft(account_id="0", mail_data=mail_data, key="draft_123")

    assert status_code == 200
    assert result["data"]["draft_key"] == "draft_123"


def test_save_draft_external_account(monkeypatch):
    """Test saving draft in external account."""
    class FakeModuleMailForDraft:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_draft(self, account_id, mail_data, key):
            return {"draft_key": "draft_789", "account": account_id}
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True, fake_mail_module_class=FakeModuleMailForDraft)
    
    mail_data = {"to": "external@example.com", "subject": "External Draft"}
    result, status_code = interface.save_draft(account_id="abc123", mail_data=mail_data)

    assert status_code == 200


def test_save_draft_module_error(monkeypatch):
    """Test error handling when draft save fails."""
    class FakeModuleMailForDraft:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_draft(self, account_id, mail_data, key):
            raise RequestException("Save failed", err.ERROR_VALIDATION_ERROR)
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForDraft)
    
    result, status_code = interface.save_draft(account_id="0", mail_data={})

    assert status_code == 400


# ========== Tests for send_mail ==========

def test_send_mail_success(monkeypatch):
    """Test sending a mail successfully."""
    class FakeModuleMailOutgoingForSend:
        def __init__(self, user, mail_settings):
            pass
        
        def send_mail(self, account_id, mail_data):
            return b"Sent mail message"
    
    class FakeModuleMailForSend:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_mail_to_folder(self, account_id, message, folder):
            return True
        
        def delete_draft_mail(self, account_id, draft_uid):
            return True
    
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMailOutgoing",
        FakeModuleMailOutgoingForSend
    )
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForSend)
    
    mail_data = {"to": "recipient@example.com", "subject": "Test", "body": "Test body"}
    result, status_code = interface.send_mail(account_id="0", mail_data=mail_data)

    assert status_code == 200


def test_send_mail_with_draft_deletion(monkeypatch):
    """Test sending mail and deleting associated draft."""
    class FakeModuleMailOutgoingForSend:
        def __init__(self, user, mail_settings):
            pass
        
        def send_mail(self, account_id, mail_data):
            return b"Sent mail message"
    
    class FakeModuleMailForSend:
        def __init__(self, user, mail_settings, process_setting=None):
            self.draft_deleted = False
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_mail_to_folder(self, account_id, message, folder):
            return True
        
        def delete_draft_mail(self, account_id, draft_uid):
            self.draft_deleted = True
            return True
    
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMailOutgoing",
        FakeModuleMailOutgoingForSend
    )
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForSend)
    
    mail_data = {"to": "recipient@example.com", "subject": "Test"}
    result, status_code = interface.send_mail(account_id="0", mail_data=mail_data, draft_uid="draft_123")

    assert status_code == 200


def test_send_mail_send_failure(monkeypatch):
    """Test error handling when mail sending fails."""
    fake_module = FakeModuleUserProfile()
    
    class FakeModuleMailOutgoingForSend:
        def __init__(self, user, mail_settings):
            pass
        
        def send_mail(self, account_id, mail_data):
            raise RequestException("SMTP error", err.ERROR_VALIDATION_ERROR)
    
    class FakeModuleMailForSend:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
    
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMailOutgoing",
        FakeModuleMailOutgoingForSend
    )
    
    interface = create_interface_with_settings(monkeypatch, fake_module, fake_mail_module_class=FakeModuleMailForSend)
    
    result, status_code = interface.send_mail(account_id="0", mail_data={})

    assert status_code == 400


def test_send_mail_external_account(monkeypatch):
    """Test sending mail from external account."""
    class FakeModuleMailOutgoingForSend:
        def __init__(self, user, mail_settings):
            pass
        
        def send_mail(self, account_id, mail_data):
            return b"Sent from external"
    
    class FakeModuleMailForSend:
        def __init__(self, user, mail_settings, process_setting=None):
            pass
        
        def get_mailbox_quota(self, account_id):
            return None
        
        def save_mail_to_folder(self, account_id, message, folder):
            return True
    
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMailOutgoing",
        FakeModuleMailOutgoingForSend
    )
    
    fake_module = FakeModuleUserProfile()
    interface = create_interface_with_settings(monkeypatch, fake_module, allow_external=True, fake_mail_module_class=FakeModuleMailForSend)
    
    mail_data = {"to": "recipient@example.com", "subject": "From External"}
    result, status_code = interface.send_mail(account_id="abc123", mail_data=mail_data)

    assert status_code == 200
# ========== Tests for search_mailbox ==========

def create_interface_with_search(monkeypatch, fake_module, allow_external=True,
                                 search_result=None, search_total=0,
                                 search_raises=None):
    """Helper to create interface with a FakeModuleMail that supports search_mails."""
    patch_module_on_interface(monkeypatch, fake_module)

    class FakeUserModuleSettings:
        def __init__(self, data):
            self.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT = allow_external

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.UserModuleSettingsObj",
        FakeUserModuleSettings
    )

    class FakeMailSettings:
        def __init__(self, data):
            pass

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.MailSettingsObj",
        FakeMailSettings
    )

    _search_result = search_result if search_result is not None else []
    _search_total = search_total
    _search_raises = search_raises

    class FakeModuleMail:
        def __init__(self, user, mail_settings, process_setting=None):
            self.search_mails_args = None

        def get_mailbox_quota(self, account_id):
            return None

        def search_mails(self, account_id, search_params, collection_param):
            self.search_mails_args = (account_id, search_params, collection_param)
            if _search_raises is not None:
                raise _search_raises
            return _search_result, _search_total

    fake_mail_module_instance = FakeModuleMail.__new__(FakeModuleMail)
    fake_mail_module_instance.search_mails_args = None

    class FakeModuleMailTracked(FakeModuleMail):
        """Tracked version that exposes the instance for assertions."""
        _instance = None
        def __init__(self, user, mail_settings, process_setting=None):
            super().__init__(user, mail_settings, process_setting)
            FakeModuleMailTracked._instance = self

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMail",
        FakeModuleMailTracked
    )

    # Patch ModuleMailOutgoing to avoid real instantiation
    class FakeModuleMailOutgoing:
        def __init__(self, user, mail_settings):
            pass

    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMailbox.ModuleMailOutgoing",
        FakeModuleMailOutgoing
    )

    process_setting = FakeProcessSetting()
    user = FakeUser()
    user_domain = {"USER_MODULE_SETTINGS": {}, "MAIL_SETTINGS": {}}

    interface = InterfaceApiMailMailbox(
        process_setting=process_setting,
        user=user,
        user_domain=user_domain
    )
    return interface, FakeModuleMailTracked


def _make_collection_param():
    """Build a minimal CollectionPaginateArgs for search tests."""
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs
    return CollectionPaginateArgs(page=1, page_size=10)


def test_search_mailbox_main_account_success(monkeypatch):
    """Test advanced search on main account returns results."""
    fake_module = FakeModuleUserProfile()
    mails = [{"uid": "1", "subject": "Hello"}, {"uid": "2", "subject": "World"}]
    interface, tracked = create_interface_with_search(
        monkeypatch, fake_module, search_result=mails, search_total=2
    )

    search_params = {"text": "Hello"}
    total, result, status_code = interface.search_mailbox("0", search_params, _make_collection_param())

    assert status_code == 200
    assert total == 2
    assert result["data"] == mails


def test_search_mailbox_empty_results(monkeypatch):
    """Test advanced search with no matching mails returns empty list."""
    fake_module = FakeModuleUserProfile()
    interface, _ = create_interface_with_search(
        monkeypatch, fake_module, search_result=[], search_total=0
    )

    total, result, status_code = interface.search_mailbox("0", {}, _make_collection_param())

    assert status_code == 200
    assert total == 0
    assert result["data"] == []


def test_search_mailbox_external_account_forbidden(monkeypatch):
    """Test that searching external account when not allowed returns 403."""
    fake_module = FakeModuleUserProfile()
    interface, _ = create_interface_with_search(
        monkeypatch, fake_module, allow_external=False
    )

    total, result, status_code = interface.search_mailbox("abc123", {}, _make_collection_param())

    assert status_code == 403
    assert total == 0
    assert result["error_code"] == err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.c


def test_search_mailbox_external_account_allowed(monkeypatch):
    """Test that searching external account when allowed succeeds."""
    fake_module = FakeModuleUserProfile()
    mails = [{"uid": "5", "subject": "External mail"}]
    interface, _ = create_interface_with_search(
        monkeypatch, fake_module, allow_external=True,
        search_result=mails, search_total=1
    )

    total, result, status_code = interface.search_mailbox("abc123", {}, _make_collection_param())

    assert status_code == 200
    assert total == 1
    assert result["data"] == mails


def test_search_mailbox_module_error_returns_error_response(monkeypatch):
    """Test that a RequestException from search_mails is caught and returned as error."""
    fake_module = FakeModuleUserProfile()
    interface, _ = create_interface_with_search(
        monkeypatch, fake_module,
        search_raises=RequestException("IMAP error", err.ERROR_IMAP_CONNECTION_FAILED)
    )

    total, result, status_code = interface.search_mailbox("0", {}, _make_collection_param())

    assert total == 0
    assert status_code >= 400
    assert "error_code" in result


def test_search_mailbox_passes_params_to_module(monkeypatch):
    """Test that search_params and collection_param are forwarded to module.search_mails."""
    fake_module = FakeModuleUserProfile()
    interface, tracked = create_interface_with_search(
        monkeypatch, fake_module, search_result=[], search_total=0
    )

    search_params = {"text": "invoice", "folders": ["INBOX"]}
    collection = _make_collection_param()
    interface.search_mailbox("0", search_params, collection)

    instance = tracked._instance
    assert instance is not None
    assert instance.search_mails_args[1] == search_params
    assert instance.search_mails_args[2] is collection
