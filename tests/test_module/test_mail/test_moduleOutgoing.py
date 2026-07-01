"""
Tests unitaires pour ModuleMailOutgoing (Module layer).
Ces tests utilisent un fake ClientOutgoing pour tester la logique métier du module.
"""
import pytest
from unittest.mock import MagicMock
from email.message import EmailMessage

from app.module.mail.ModuleMailOutgoing import ModuleMailOutgoing
from app.utils import constants as cs
from app.utils.exceptions import RequestException


ACCOUNT_ID_DEFAULT = cs.DEFAULT_IDENTITY_KEY_VALUE  # "0"
ACCOUNT_ID_EXTERNAL = "ext_account_123"


class FakeClientOutgoing:
    """Fake ClientOutgoing for testing ModuleMailOutgoing."""

    def __init__(self):
        self.connected = False
        self.authenticated = False

        # Call tracking
        self.connect_calls = 0
        self.login_calls = []
        self.send_mail_calls = []

        # Configurable to raise
        self.connect_raises = None
        self.login_raises = None
        self.send_mail_raises = None

    def connect(self):
        self.connect_calls += 1
        if self.connect_raises:
            raise self.connect_raises
        self.connected = True

    def login(self, username, password, authname=""):
        self.login_calls.append((username, password, authname))
        if self.login_raises:
            raise self.login_raises
        self.authenticated = True

    def send_mail(self, message):
        self.send_mail_calls.append(message)
        if self.send_mail_raises:
            raise self.send_mail_raises


def _make_module(monkeypatch, fake_client=None):
    """Create a ModuleMailOutgoing with mocked User/MailSettings and patched _open_client_for."""
    if fake_client is None:
        fake_client = FakeClientOutgoing()

    mock_user = MagicMock()
    mock_user.login_mail_outgoing = "user@example.com"
    mock_user.password = "userpassword"
    mock_user.profile.external_accounts = {}

    mock_mail_settings = MagicMock()
    mock_mail_settings.SOGO_D_MAIL_OUTGOING_TYPE = "smtp"
    mock_mail_settings.SOGO_D_SMTP_MASTER_ENABLED = False
    mock_mail_settings.SOGO_D_SMTP_SERVER = "smtp.example.com"
    mock_mail_settings.SOGO_D_SMTP_PORT = 587
    mock_mail_settings.SOGO_D_SMTP_ENCRYPTION = "starttls"
    mock_mail_settings.SOGO_D_SMTP_AUTH_MECH = "plain"

    module = ModuleMailOutgoing(user=mock_user, mail_settings=mock_mail_settings)
    monkeypatch.setattr(module, "_open_client_for", lambda account_id, do_login=True: fake_client)
    return module, fake_client


# ========== Tests for initialization ==========

def test_module_init_success():
    """Test ModuleMailOutgoing initialization with valid mocked objects."""
    mock_user = MagicMock()
    mock_mail_settings = MagicMock()
    module = ModuleMailOutgoing(user=mock_user, mail_settings=mock_mail_settings)
    assert module.user is mock_user
    assert module.mail_settings is mock_mail_settings


def test_module_init_without_args_raises():
    """Test ModuleMailOutgoing initialization without arguments raises TypeError."""
    with pytest.raises(TypeError):
        ModuleMailOutgoing()


# ========== Tests for _get_outgoing_conf ==========

def test_get_outgoing_conf_default_smtp(monkeypatch):
    """Test _get_outgoing_conf for the main account with smtp type."""
    monkeypatch.setattr("app.module.mail.ModuleMailOutgoing.decrypt_password", lambda p: p)

    mock_user = MagicMock()
    mock_user.login_mail_outgoing = "user@example.com"
    mock_user.password = "secret"

    mock_settings = MagicMock()
    mock_settings.SOGO_D_MAIL_OUTGOING_TYPE = "smtp"
    mock_settings.SOGO_D_SMTP_MASTER_ENABLED = False
    mock_settings.SOGO_D_SMTP_SERVER = "smtp.example.com"
    mock_settings.SOGO_D_SMTP_PORT = 587
    mock_settings.SOGO_D_SMTP_ENCRYPTION = "starttls"
    mock_settings.SOGO_D_SMTP_AUTH_MECH = "plain"

    module = ModuleMailOutgoing(user=mock_user, mail_settings=mock_settings)
    conf = module._get_outgoing_conf(ACCOUNT_ID_DEFAULT)

    assert conf["type"] == "smtp"
    assert conf["username"] == "user@example.com"
    assert conf["password"] == "secret"
    assert conf["authname"] == ""
    assert conf["args"]["server"] == "smtp.example.com"
    assert conf["args"]["port"] == 587
    assert conf["args"]["encryption"] == "starttls"
    assert conf["args"]["auth_mech"] == "plain"


def test_get_outgoing_conf_default_smtp_master_enabled(monkeypatch):
    """Test _get_outgoing_conf uses master credentials when is_system=True and master is enabled."""
    monkeypatch.setattr(
        "app.module.mail.ModuleMailOutgoing.decrypt_password",
        lambda p: f"decrypted:{p}"
    )

    mock_user = MagicMock()
    mock_user.login_mail_outgoing = "user@example.com"
    mock_user.password = "userpassword"

    mock_settings = MagicMock()
    mock_settings.SOGO_D_MAIL_OUTGOING_TYPE = "smtp"
    mock_settings.SOGO_D_SMTP_MASTER_ENABLED = True
    mock_settings.SOGO_D_SMTP_MASTER_LOGIN = "master@example.com"
    mock_settings.SOGO_D_SMTP_MASTER_PWD = "encryptedpwd"
    mock_settings.SOGO_D_SMTP_SERVER = "smtp.example.com"
    mock_settings.SOGO_D_SMTP_PORT = 587
    mock_settings.SOGO_D_SMTP_ENCRYPTION = "starttls"
    mock_settings.SOGO_D_SMTP_AUTH_MECH = "plain"

    module = ModuleMailOutgoing(user=mock_user, mail_settings=mock_settings)
    conf = module._get_outgoing_conf(ACCOUNT_ID_DEFAULT, is_system=True)

    assert conf["username"] == "master@example.com"
    assert conf["password"] == "decrypted:encryptedpwd"
    # authname must carry the real user login so the server can impersonate
    assert conf["authname"] == "user@example.com"


def test_get_outgoing_conf_default_smtp_master_disabled_is_system(monkeypatch):
    """Test _get_outgoing_conf uses user credentials when is_system=True but master is disabled."""
    monkeypatch.setattr("app.module.mail.ModuleMailOutgoing.decrypt_password", lambda p: p)

    mock_user = MagicMock()
    mock_user.login_mail_outgoing = "user@example.com"
    mock_user.password = "userpassword"

    mock_settings = MagicMock()
    mock_settings.SOGO_D_MAIL_OUTGOING_TYPE = "smtp"
    mock_settings.SOGO_D_SMTP_MASTER_ENABLED = False
    mock_settings.SOGO_D_SMTP_SERVER = "smtp.example.com"
    mock_settings.SOGO_D_SMTP_PORT = 465
    mock_settings.SOGO_D_SMTP_ENCRYPTION = "ssl"
    mock_settings.SOGO_D_SMTP_AUTH_MECH = "login"

    module = ModuleMailOutgoing(user=mock_user, mail_settings=mock_settings)
    conf = module._get_outgoing_conf(ACCOUNT_ID_DEFAULT, is_system=True)

    assert conf["username"] == "user@example.com"
    assert conf["password"] == "userpassword"
    assert conf["authname"] == ""


def test_get_outgoing_conf_default_sendmail(monkeypatch):
    """Test _get_outgoing_conf for the main account with sendmail type."""
    monkeypatch.setattr("app.module.mail.ModuleMailOutgoing.decrypt_password", lambda p: p)

    mock_user = MagicMock()
    mock_user.login_mail_outgoing = "user@example.com"
    mock_user.password = "secret"

    mock_settings = MagicMock()
    mock_settings.SOGO_D_MAIL_OUTGOING_TYPE = "sendmail"

    module = ModuleMailOutgoing(user=mock_user, mail_settings=mock_settings)
    conf = module._get_outgoing_conf(ACCOUNT_ID_DEFAULT)

    assert conf["type"] == "sendmail"
    assert conf["args"] == {}
    assert conf["authname"] == ""
    assert conf["username"] == "user@example.com"


def test_get_outgoing_conf_external_account_found(monkeypatch):
    """Test _get_outgoing_conf for an external account that exists."""
    monkeypatch.setattr(
        "app.module.mail.ModuleMailOutgoing.decrypt_password",
        lambda p: f"dec:{p}"
    )

    mock_user = MagicMock()
    mock_user.profile.external_accounts = {
        ACCOUNT_ID_EXTERNAL: {
            "mail_outgoing": {
                "type": "smtp",
                "username": "ext@remote.com",
                "password": "encpwd",
                "server": "smtp.remote.com",
                "port": 465,
                "encryption": "ssl",
                "auth_mech": "login",
            }
        }
    }

    module = ModuleMailOutgoing(user=mock_user, mail_settings=MagicMock())
    conf = module._get_outgoing_conf(ACCOUNT_ID_EXTERNAL)

    assert conf["type"] == "smtp"
    assert conf["username"] == "ext@remote.com"
    assert conf["password"] == "dec:encpwd"
    assert conf["authname"] == ""
    assert conf["args"]["server"] == "smtp.remote.com"
    assert conf["args"]["port"] == 465
    assert conf["args"]["encryption"] == "ssl"
    assert conf["args"]["auth_mech"] == "login"


def test_get_outgoing_conf_external_account_not_found():
    """Test _get_outgoing_conf raises RequestException when external account is missing."""
    mock_user = MagicMock()
    mock_user.profile.external_accounts = {"other_account": {}}

    module = ModuleMailOutgoing(user=mock_user, mail_settings=MagicMock())

    with pytest.raises(RequestException):
        module._get_outgoing_conf("nonexistent_account")


def test_get_outgoing_conf_external_accounts_is_none():
    """Test _get_outgoing_conf raises RequestException when external_accounts is None."""
    mock_user = MagicMock()
    mock_user.profile.external_accounts = None

    module = ModuleMailOutgoing(user=mock_user, mail_settings=MagicMock())

    with pytest.raises(RequestException):
        module._get_outgoing_conf("any_external_account")


def test_get_outgoing_conf_external_accounts_is_empty():
    """Test _get_outgoing_conf raises RequestException when external_accounts is empty."""
    mock_user = MagicMock()
    mock_user.profile.external_accounts = {}

    module = ModuleMailOutgoing(user=mock_user, mail_settings=MagicMock())

    with pytest.raises(RequestException):
        module._get_outgoing_conf("any_external_account")


# ========== Tests for send_mail ==========

def test_send_mail_basic_html(monkeypatch):
    """Test send_mail with a basic HTML email."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Hello",
        "body": "<p>Hello world</p>",
        "is_html": True,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert isinstance(result, EmailMessage)
    assert result["From"] == "sender@example.com"
    assert result["To"] == "recipient@example.com"
    assert result["Subject"] == "Hello"
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_plain_text(monkeypatch):
    """Test send_mail with plain text body."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Plain text mail",
        "body": "Hello world",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert isinstance(result, EmailMessage)
    assert result["Subject"] == "Plain text mail"
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_multiple_recipients(monkeypatch):
    """Test send_mail with multiple To recipients."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["a@example.com", "b@example.com", "c@example.com"],
        "subject": "Multi-recipient",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert "a@example.com" in result["To"]
    assert "b@example.com" in result["To"]
    assert "c@example.com" in result["To"]


def test_send_mail_with_cc(monkeypatch):
    """Test send_mail includes Cc header when cc is provided."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "cc": ["cc1@example.com", "cc2@example.com"],
        "subject": "With CC",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert result["Cc"] is not None
    assert "cc1@example.com" in result["Cc"]
    assert "cc2@example.com" in result["Cc"]


def test_send_mail_without_cc(monkeypatch):
    """Test send_mail does not add Cc header when cc is absent."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "No CC",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["Cc"] is None


def test_send_mail_with_bcc(monkeypatch):
    """Test send_mail includes Bcc header when bcc is provided."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "bcc": ["bcc@example.com"],
        "subject": "With BCC",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert result["Bcc"] is not None
    assert "bcc@example.com" in result["Bcc"]


def test_send_mail_without_bcc(monkeypatch):
    """Test send_mail does not add Bcc header when bcc is absent."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "No BCC",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["Bcc"] is None


def test_send_mail_with_return_receipt(monkeypatch):
    """Test send_mail sets return receipt headers when return_receipt is True."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Receipt requested",
        "body": "Hello",
        "is_html": False,
        "return_receipt": True,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert result["Disposition-Notification-To"] is not None
    assert result["Return-Receipt-To"] is not None


def test_send_mail_without_return_receipt(monkeypatch):
    """Test send_mail does not set return receipt headers when return_receipt is False."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "No receipt",
        "body": "Hello",
        "is_html": False,
        "return_receipt": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert result["Disposition-Notification-To"] is None
    assert result["Return-Receipt-To"] is None


def test_send_mail_with_priority(monkeypatch):
    """Test send_mail sets X-Priority header when priority is provided."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "High priority",
        "body": "Urgent!",
        "is_html": False,
        "priority": 1,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["X-Priority"] == "1"


def test_send_mail_without_priority(monkeypatch):
    """Test send_mail does not set X-Priority header when priority is absent."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Normal priority",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["X-Priority"] is None


def test_send_mail_with_reply_to(monkeypatch):
    """Test send_mail sets Reply-To header when reply_to is provided."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Reply-To test",
        "body": "Hello",
        "is_html": False,
        "reply_to": "replyto@example.com",
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["Reply-To"] == "replyto@example.com"


def test_send_mail_without_reply_to(monkeypatch):
    """Test send_mail does not set Reply-To header when reply_to is absent."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "No Reply-To",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["Reply-To"] is None


def test_send_mail_has_message_id(monkeypatch):
    """Test send_mail always generates a Message-ID header."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Message ID test",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["Message-ID"] is not None
    assert "@" in result["Message-ID"]


def test_send_mail_has_date(monkeypatch):
    """Test send_mail always sets a Date header."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Date test",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert result["Date"] is not None


def test_send_mail_with_extra_headers(monkeypatch):
    """Test send_mail injects extra RFC 5322 headers not already present."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Thread reply",
        "body": "Hello",
        "is_html": False,
    }
    extra_headers = {
        "In-Reply-To": "<original@example.com>",
        "References": "<original@example.com>",
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data, extra_headers=extra_headers)

    assert result["In-Reply-To"] == "<original@example.com>"
    assert result["References"] == "<original@example.com>"


def test_send_mail_extra_headers_do_not_overwrite_from(monkeypatch):
    """Test send_mail extra headers cannot overwrite the From header."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Overwrite test",
        "body": "Hello",
        "is_html": False,
    }
    extra_headers = {"From": "attacker@evil.com"}

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data, extra_headers=extra_headers)
    assert result["From"] == "sender@example.com"


def test_send_mail_extra_headers_do_not_overwrite_subject(monkeypatch):
    """Test send_mail extra headers cannot overwrite the Subject header."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Real Subject",
        "body": "Hello",
        "is_html": False,
    }
    extra_headers = {"Subject": "Injected Subject"}

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data, extra_headers=extra_headers)
    assert result["Subject"] == "Real Subject"


def test_send_mail_without_extra_headers(monkeypatch):
    """Test send_mail works correctly when extra_headers is None."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "No extra headers",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data, extra_headers=None)
    assert isinstance(result, EmailMessage)
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_with_attachment(monkeypatch):
    """Test send_mail adds an attachment correctly."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "With attachment",
        "body": "See attached",
        "is_html": False,
        "attachments": [
            {"data": b"file content", "filename": "test.txt"}
        ],
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert isinstance(result, EmailMessage)
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_with_multiple_attachments(monkeypatch):
    """Test send_mail handles multiple attachments."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Two attachments",
        "body": "See attached",
        "is_html": False,
        "attachments": [
            {"data": b"content one", "filename": "file1.txt"},
            {"data": b"content two", "filename": "file2.pdf"},
        ],
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert isinstance(result, EmailMessage)
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_attachment_missing_data_key(monkeypatch):
    """Test send_mail raises RequestException when attachment dict is missing the 'data' key."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Bad attachment",
        "body": "See attached",
        "is_html": False,
        "attachments": [
            {"filename": "test.txt"}  # missing 'data'
        ],
    }

    with pytest.raises(RequestException):
        module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)


def test_send_mail_empty_attachments_list(monkeypatch):
    """Test send_mail works correctly when attachments is an empty list."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "No attachments",
        "body": "Hello",
        "is_html": False,
        "attachments": [],
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert isinstance(result, EmailMessage)
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_attachments_none(monkeypatch):
    """Test send_mail works correctly when attachments is None."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "None attachments",
        "body": "Hello",
        "is_html": False,
        "attachments": None,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)
    assert isinstance(result, EmailMessage)
    assert len(fake_client.send_mail_calls) == 1


def test_send_mail_delegates_to_send_raw_message(monkeypatch):
    """Test send_mail delegates the actual sending to send_raw_message."""
    module, fake_client = _make_module(monkeypatch)
    send_raw_calls = []
    original_send_raw = module.send_raw_message

    def spy_send_raw(account_id, message):
        send_raw_calls.append((account_id, message))
        original_send_raw(account_id, message)

    monkeypatch.setattr(module, "send_raw_message", spy_send_raw)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Delegation test",
        "body": "Hello",
        "is_html": False,
    }

    module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert len(send_raw_calls) == 1
    assert send_raw_calls[0][0] == ACCOUNT_ID_DEFAULT
    assert isinstance(send_raw_calls[0][1], EmailMessage)


def test_send_mail_returns_built_message(monkeypatch):
    """Test send_mail returns the EmailMessage that was sent."""
    module, fake_client = _make_module(monkeypatch)

    mail_data = {
        "from_addr": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Return value test",
        "body": "Hello",
        "is_html": False,
    }

    result = module.send_mail(ACCOUNT_ID_DEFAULT, mail_data)

    assert isinstance(result, EmailMessage)
    # The returned message must be the same object sent to the client
    assert fake_client.send_mail_calls[0] is result


# ========== Tests for send_raw_message ==========

def test_send_raw_message_success(monkeypatch):
    """Test send_raw_message sends a pre-built message through the client."""
    module, fake_client = _make_module(monkeypatch)

    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Raw message test"
    message.set_content("Hello")

    module.send_raw_message(ACCOUNT_ID_DEFAULT, message)

    assert len(fake_client.send_mail_calls) == 1
    assert fake_client.send_mail_calls[0]["Subject"] == "Raw message test"


def test_send_raw_message_passes_message_unchanged(monkeypatch):
    """Test send_raw_message forwards the exact message object to the client."""
    module, fake_client = _make_module(monkeypatch)

    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Unchanged message"
    message.set_content("body")

    module.send_raw_message(ACCOUNT_ID_DEFAULT, message)

    assert fake_client.send_mail_calls[0] is message


def test_send_raw_message_client_error(monkeypatch):
    """Test send_raw_message propagates errors raised by the client."""
    module, fake_client = _make_module(monkeypatch)
    fake_client.send_mail_raises = RequestException("SMTP connection lost")

    message = EmailMessage()
    message["Subject"] = "Error test"
    message.set_content("body")

    with pytest.raises(RequestException, match="SMTP connection lost"):
        module.send_raw_message(ACCOUNT_ID_DEFAULT, message)


def test_send_raw_message_external_account(monkeypatch):
    """Test send_raw_message works for an external account."""
    module, fake_client = _make_module(monkeypatch)

    message = EmailMessage()
    message["From"] = "ext@remote.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "External raw send"
    message.set_content("body")

    module.send_raw_message(ACCOUNT_ID_EXTERNAL, message)

    assert len(fake_client.send_mail_calls) == 1
    assert fake_client.send_mail_calls[0]["Subject"] == "External raw send"
