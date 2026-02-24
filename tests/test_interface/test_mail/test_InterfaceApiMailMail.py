import pytest
from app.interface.mail.InterfaceApiMailMail import InterfaceApiMailMail
from app.utils.exceptions import RequestException
from app.utils import errors as err

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
        self.reply_mail_result = {"reply": "Reply draft created"}
        self.forward_mail_result = {"forward": "Forward draft created"}

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

    def reply_mail(self, folder_name, mail_uid):
        """Reply to a mail."""
        self.reply_mail_args = (folder_name, mail_uid)
        return self.reply_mail_result

    def forward_mail(self, folder_name, mail_uid):
        """Forward a mail."""
        self.forward_mail_args = (folder_name, mail_uid)
        return self.forward_mail_result

    # NotImplemented methods (kept for reference but now implemented above)
    # def reply_mail(self, folder_name, mail_uid):
    #     raise NotImplementedError("reply_mail is not implemented yet")

    # def forward_mail(self, folder_name, mail_uid):
    #     raise NotImplementedError("forward_mail is not implemented yet")


def patch_module_on_interface(monkeypatch, fake_module):
    """
    Patch the ModuleMail class in the InterfaceApiMailMail module with a fake module.
    """
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailMail.ModuleMail",
        lambda user_conf=None: fake_module
    )

# ========== Tests for get_mail_list ==========

def test_get_mail_list_success(monkeypatch):
    """Test fetching mail list for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    total, result, status_code = interface.get_mail_list(account_id=0, folder_name="INBOX", first=0, last=10)

    assert status_code == 200
    assert total == 100
    assert result["data"] == [{"uid": 1, "subject": "Test"}]
    assert fake_module.get_folder_mails_args == ("INBOX", 0, 10)

def test_get_mail_list_invalid_account_id(monkeypatch):
    """Test error handling for invalid account ID."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    total, result, status_code = interface.get_mail_list(account_id=5, folder_name="INBOX", first=0, last=10)

    assert status_code >= 500
    assert total == 0
    # The error_msg comes from the error_msg dict for ERROR_UNKOWN
    assert result["error_code"] == "S999999"
    assert result["error_msg"] == "Undefined Error"

def test_get_mail_list_module_exception(monkeypatch):
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_mails = lambda *args: (_ for _ in ()).throw(RequestException("Connection failed", err.ERROR_IMAP_CONNECTION_FAILED))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    total, result, status_code = interface.get_mail_list(account_id=0, folder_name="INBOX", first=0, last=10)

    assert result["error_code"] == "S000311"
    assert status_code >= 500
    assert total == 0

# ========== Tests for get_mail_detail ==========

def test_get_mail_detail_success(monkeypatch):
    """Test fetching mail details for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.get_mail_detail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["uid"] == 42
    assert result["data"]["subject"] == "Test Subject"
    assert fake_module.get_mail_detail_args == ("INBOX", 42)

def test_get_mail_detail_module_error(monkeypatch):
    """Test error handling when mail detail fetch fails."""
    fake_module = FakeModuleMail()
    fake_module.get_mail_detail = lambda *args: (_ for _ in ()).throw(RequestException("Mail not found", err.ERROR_MAIL_UID_NOT_FOUND))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.get_mail_detail(account_id=0, folder_name="INBOX", mail_uid=999)

    assert result["error_code"] == "S000303"
    assert status_code == 404

# ========== Tests for delete_mail ==========

def test_delete_mail_success(monkeypatch):
    """Test deleting a mail for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.delete_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result["data"]["uid_deleted"] == 42
    assert status_code == 204
    assert fake_module.delete_mail_args == ("INBOX", 42)

def test_delete_mail_module_error(monkeypatch):
    """Test error handling when mail deletion fails."""
    fake_module = FakeModuleMail()
    fake_module.delete_mail = lambda *args: (_ for _ in ()).throw(RequestException("Cannot delete", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.delete_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 400
    assert result["error_code"] == "S000300"

# ========== Tests for get_mail_raw ==========

def test_get_mail_raw_success(monkeypatch):
    """Test fetching raw mail content for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.get_mail_raw(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["raw"] == "Raw email content"
    assert fake_module.get_mail_raw_args == ("INBOX", 42)

def test_get_mail_raw_module_error(monkeypatch):
    """Test error handling when raw mail fetch fails."""
    fake_module = FakeModuleMail()
    fake_module.get_mail_raw = lambda *args: (_ for _ in ()).throw(RequestException("Cannot fetch raw", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.get_mail_raw(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result["error_code"] == "S000300"
    assert status_code == 400

# ========== Tests for _get_user_conf ==========

def test_get_user_conf_no_config():
    """Test error when no user conf is provided."""
    interface = InterfaceApiMailMail(user_conf=None)

    with pytest.raises(RequestException, match="No mailbox configuration available"):
        interface._get_user_conf(0)

def test_get_user_conf_missing_fields():
    """Test error when user conf is missing required fields."""
    user_conf = {"username": "test@example.com"}  # missing password and type
    interface = InterfaceApiMailMail(user_conf=user_conf)

    with pytest.raises(RequestException, match="Missing fields"):
        interface._get_user_conf(0)

def test_get_user_conf_list_config():
    """Test getting user conf from a list."""
    user_conf = [
        {"username": "test1@example.com", "password": "pass1", "type": "imap"},
        {"username": "test2@example.com", "password": "pass2", "type": "imap"}
    ]
    interface = InterfaceApiMailMail(user_conf=user_conf)

    conf = interface._get_user_conf(1)

    assert conf["username"] == "test2@example.com"


# ========== Tests for reply_mail ==========

def test_reply_mail_success(monkeypatch):
    """Test replying to a mail for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.reply_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["reply"] == "Reply draft created"
    assert fake_module.reply_mail_args == ("INBOX", 42)


def test_reply_mail_module_error(monkeypatch):
    """Test error handling when replying to mail fails."""
    fake_module = FakeModuleMail()
    fake_module.reply_mail = lambda *args: (_ for _ in ()).throw(RequestException("Cannot reply", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.reply_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for forward_mail ==========

def test_forward_mail_success(monkeypatch):
    """Test forwarding a mail for a valid account."""
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.forward_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["forward"] == "Forward draft created"
    assert fake_module.forward_mail_args == ("INBOX", 42)


def test_forward_mail_module_error(monkeypatch):
    """Test error handling when forwarding mail fails."""
    fake_module = FakeModuleMail()
    fake_module.forward_mail = lambda *args: (_ for _ in ()).throw(RequestException("Cannot forward", err.ERROR_VALIDATION_ERROR))
    patch_module_on_interface(monkeypatch, fake_module)
    user_conf = {"username": "test@example.com", "password": "pass", "type": "imap"}
    interface = InterfaceApiMailMail(user_conf=user_conf)

    result, status_code = interface.forward_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result["error_code"] == "S000300"
    assert status_code == 400
