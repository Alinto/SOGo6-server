import pytest
from app.interface.mail.InterfaceApiMailMail import InterfaceApiMailMail
from app.utils.exceptions import RequestException

class FakeModuleMail:
    """
    Fake ModuleMail for testing InterfaceApiMailMail.
    """
    def __init__(self, user_conf=None):
        self.user_conf = user_conf
        # --- Memorisation des args pour vérification ---
        self.get_folder_mails_args = None
        self.get_mail_detail_args = None
        self.delete_mail_args = None
        self.get_mail_raw_args = None

        # --- Résultats configurables par test ---
        self.get_folder_mails_result = ([{"uid": 1, "subject": "Test"}], 100)
        self.get_mail_detail_result = {
            "uid": 42,
            "subject": "Test Subject",
            "from": "john@example.com",
            "body": "Test body"
        }
        self.delete_mail_result = {"uid_deleted": 42}
        self.get_mail_raw_result = {"raw": "Raw email content"}

    def get_folder_mails(self, folder_name, first, last):
        """Fetch a list of mails from a folder."""
        self.get_folder_mails_args = (folder_name, first, last)
        return self.get_folder_mails_result

    def get_mail_detail(self, folder_name, mail_uid):
        """Fetch the details of a specific mail."""
        self.get_mail_detail_args = (folder_name, mail_uid)
        return self.get_mail_detail_result

    def delete_mail(self, folder_name, mail_uid):
        """Delete a specific mail."""
        self.delete_mail_args = (folder_name, mail_uid)
        return self.delete_mail_result

    def get_mail_raw(self, folder_name, mail_uid):
        """Get raw mail content."""
        self.get_mail_raw_args = (folder_name, mail_uid)
        return self.get_mail_raw_result

    # NotImplemented methods
    def reply_mail(self, folder_name, mail_uid):
        raise NotImplementedError("reply_mail is not implemented yet")

    def forward_mail(self, folder_name, mail_uid):
        raise NotImplementedError("forward_mail is not implemented yet")


def patch_module_on_interface(monkeypatch, fake_module):
    """
    Patch the ModuleMail class in the InterfaceApiMailMail module with a fake module.
    """
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMail.ModuleMail",
        lambda user_conf=None: fake_module
    )

# ========== Tests for get_mail_list ==========

def test_given_valid_account_when_get_mail_list_then_success(monkeypatch):
    """Test fetching mail list for a valid account."""
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    total, result, status_code = interface.get_mail_list(account_id=0, folder_name="INBOX", first=0, last=10)
    # Then
    assert status_code == 200
    assert total == 100
    assert result["data"]["mails"] == [{"uid": 1, "subject": "Test"}]
    assert fake_module.get_folder_mails_args == ("INBOX", 0, 10)

def test_given_invalid_account_id_when_get_mail_list_then_error(monkeypatch):
    """Test error handling for invalid account ID."""
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    total, result, status_code = interface.get_mail_list(account_id=5, folder_name="INBOX", first=0, last=10)
    # Then
    assert status_code >= 400
    assert total == 0
    # The error_msg comes from the error_msg dict for ERROR_UNKOWN
    assert result["error_code"] == 99999
    assert result["error_msg"] == "Error has not been defined"

def test_given_module_exception_when_get_mail_list_then_error(monkeypatch):
    """Test error handling when module raises RequestException."""
    # Given
    fake_module = FakeModuleMail()
    fake_module.get_folder_mails = lambda *args: (_ for _ in ()).throw(RequestException("Connection failed", 311))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    total, result, status_code = interface.get_mail_list(account_id=0, folder_name="INBOX", first=0, last=10)
    # Then
    assert status_code >= 400
    assert total == 0

# ========== Tests for get_mail_detail ==========

def test_given_valid_account_when_get_mail_detail_then_success(monkeypatch):
    """Test fetching mail details for a valid account."""
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    result, status_code = interface.get_mail_detail(account_id=0, folder_name="INBOX", mail_uid=42)
    # Then
    assert status_code == 200
    assert result["data"]["uid"] == 42
    assert result["data"]["subject"] == "Test Subject"
    assert fake_module.get_mail_detail_args == ("INBOX", 42)

def test_given_module_error_when_get_mail_detail_then_error(monkeypatch):
    """Test error handling when mail detail fetch fails."""
    # Given
    fake_module = FakeModuleMail()
    fake_module.get_mail_detail = lambda *args: (_ for _ in ()).throw(RequestException("Mail not found", 404))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    result, status_code = interface.get_mail_detail(account_id=0, folder_name="INBOX", mail_uid=999)
    # Then
    assert status_code >= 400

# ========== Tests for delete_mail ==========

def test_given_valid_account_when_delete_mail_then_success(monkeypatch):
    """Test deleting a mail for a valid account."""
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    result, status_code = interface.delete_mail(account_id=0, folder_name="INBOX", mail_uid=42)
    # Then
    assert status_code == 204
    assert fake_module.delete_mail_args == ("INBOX", 42)

def test_given_module_error_when_delete_mail_then_error(monkeypatch):
    """Test error handling when mail deletion fails."""
    # Given
    fake_module = FakeModuleMail()
    fake_module.delete_mail = lambda *args: (_ for _ in ()).throw(RequestException("Cannot delete", 400))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    result, status_code = interface.delete_mail(account_id=0, folder_name="INBOX", mail_uid=42)
    # Then
    assert status_code >= 400

# ========== Tests for get_mail_raw ==========

def test_given_valid_account_when_get_mail_raw_then_success(monkeypatch):
    """Test fetching raw mail content for a valid account."""
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    result, status_code = interface.get_mail_raw(account_id=0, folder_name="INBOX", mail_uid=42)
    # Then
    assert status_code == 200
    assert result["data"]["raw"] == "Raw email content"
    assert fake_module.get_mail_raw_args == ("INBOX", 42)

def test_given_module_error_when_get_mail_raw_then_error(monkeypatch):
    """Test error handling when raw mail fetch fails."""
    # Given
    fake_module = FakeModuleMail()
    fake_module.get_mail_raw = lambda *args: (_ for _ in ()).throw(RequestException("Cannot fetch raw", 400))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    result, status_code = interface.get_mail_raw(account_id=0, folder_name="INBOX", mail_uid=42)
    # Then
    assert status_code >= 400

# ========== Tests for _get_user_conf ==========

def test_given_no_user_conf_when_get_user_conf_then_error():
    """Test error when no user conf is provided."""
    # Given
    interface = InterfaceApiMailMail(user_conf=None)
    # When/Then
    with pytest.raises(RequestException, match="No mailbox configuration available"):
        interface._get_user_conf(0)

def test_given_missing_fields_when_get_user_conf_then_error():
    """Test error when user conf is missing required fields."""
    # Given
    user_conf = {"username": "test@example.com"}  # missing password and type
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When/Then
    with pytest.raises(RequestException, match="Missing fields"):
        interface._get_user_conf(0)

def test_given_list_user_conf_when_get_user_conf_then_success():
    """Test getting user conf from a list."""
    # Given
    user_conf = [
        {"username": "test1@example.com", "password": "pass1", "type": "imap"},
        {"username": "test2@example.com", "password": "pass2", "type": "imap"}
    ]
    interface = InterfaceApiMailMail(user_conf=user_conf)
    # When
    conf = interface._get_user_conf(1)
    # Then
    assert conf["username"] == "test2@example.com"
