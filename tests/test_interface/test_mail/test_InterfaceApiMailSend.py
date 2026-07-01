# pylint: disable=invalid-sequence-index
from app.interface.mail.InterfaceApiMailSend import InterfaceApiMailSend
from app.utils.exceptions import RequestException
from app.utils import errors as err


class InterfaceApiMailSendWithInjectedConf(InterfaceApiMailSend):
    """Subclass of InterfaceApiMailSend that allows injecting modules directly for testing."""

    def __init__(self, mail_module, mail_outgoing_module):
        """Initialize with injected modules for testing.

        Does not call the parent __init__ to avoid requiring all the parameters it needs.
        The modules are set directly so tests can inject fake/mock modules.
        """
        self.mail_module = mail_module  # noqa: SLF001
        self.mail_outgoing_module = mail_outgoing_module  # noqa: SLF001
        self.user = _FakeUser()


class _FakeUser:
    uid = "testuser"


class FakeModuleMail:
    """
    Fake ModuleMail for testing InterfaceApiMailSend.
    All methods mirror the ModuleMail signature.
    """

    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.save_draft_args = None
        self.validate_tmp_draft_key_args = None
        self.get_headers_from_tmp_draft_args = None
        self.get_attachments_from_tmp_draft_args = None
        self.save_mail_to_folder_args = None
        self.delete_tmp_draft_args = None
        self.delete_draft_and_tmp_args = None
        self.list_current_drafts_args = None
        self.upload_attachment_args = None
        self.delete_attachment_args = None
        self.download_draft_attachment_args = None

        # --- Résultats configurables par test ---
        self.save_draft_result = {"key": "abc123", "imap_uid": "10"}
        self.get_headers_from_tmp_draft_result = {"In-Reply-To": "<msg@example.com>"}
        self.get_attachments_from_tmp_draft_result = []
        self.list_current_drafts_result = [{"key": "abc123", "subject": "Draft 1"}]
        self.upload_attachment_result = {"key": "abc123", "filename": "file.pdf"}
        self.download_draft_attachment_result = (b"raw bytes", "application/pdf")

    def save_draft(self, account_id, mail_data, key, close=False):
        self.save_draft_args = (account_id, mail_data, key, close)
        return self.save_draft_result

    def validate_tmp_draft_key(self, key):
        self.validate_tmp_draft_key_args = (key,)

    def get_headers_from_tmp_draft(self, key):
        self.get_headers_from_tmp_draft_args = (key,)
        return self.get_headers_from_tmp_draft_result

    def get_attachments_from_tmp_draft(self, account_id, key):
        self.get_attachments_from_tmp_draft_args = (account_id, key)
        return self.get_attachments_from_tmp_draft_result

    def save_mail_to_folder(self, account_id, message, folder):
        self.save_mail_to_folder_args = (account_id, message, folder)

    def delete_tmp_draft(self, key, account_id):
        self.delete_tmp_draft_args = (key, account_id)

    def delete_draft_and_tmp(self, account_id, key):
        self.delete_draft_and_tmp_args = (account_id, key)

    def list_current_drafts(self):
        self.list_current_drafts_args = ()
        return self.list_current_drafts_result

    def upload_attachment(self, account_id, filename, content_type, file_data, key):
        self.upload_attachment_args = (account_id, filename, content_type, file_data, key)
        return self.upload_attachment_result

    def delete_attachment(self, account_id, key, filename):
        self.delete_attachment_args = (account_id, key, filename)

    def download_draft_attachment(self, account_id, key, filename):
        self.download_draft_attachment_args = (account_id, key, filename)
        return self.download_draft_attachment_result


class FakeModuleMailOutgoing:
    """
    Fake ModuleMailOutgoing for testing InterfaceApiMailSend.
    """

    def __init__(self):
        self.send_mail_args = None
        self.send_mail_result = object()  # Opaque message object

    def send_mail(self, account_id, mail_data, extra_headers=None):
        self.send_mail_args = (account_id, mail_data, extra_headers)
        return self.send_mail_result


def make_interface(fake_mail_module=None, fake_outgoing_module=None):
    """Create an InterfaceApiMailSendWithInjectedConf with the given fake modules."""
    if fake_mail_module is None:
        fake_mail_module = FakeModuleMail()
    if fake_outgoing_module is None:
        fake_outgoing_module = FakeModuleMailOutgoing()
    return InterfaceApiMailSendWithInjectedConf(fake_mail_module, fake_outgoing_module)


# ========== Tests for save_draft ==========

def test_save_draft_success_no_key():
    """Test saving a draft without an existing key."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    mail_data = {"subject": "Hello", "to": ["bob@example.com"], "body": "Hi"}
    result, status_code = interface.save_draft(account_id="0", mail_data=mail_data)

    assert status_code == 200
    assert result["data"]["key"] == "abc123"
    assert fake_mail.save_draft_args == ("0", mail_data, None, False)


def test_save_draft_success_with_key():
    """Test saving a draft with an existing key."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    mail_data = {"subject": "Hello", "to": ["bob@example.com"], "body": "Hi"}
    result, status_code = interface.save_draft(account_id="0", mail_data=mail_data, key="abc123")

    assert status_code == 200
    assert result["data"]["key"] == "abc123"
    assert fake_mail.save_draft_args == ("0", mail_data, "abc123", False)


def test_save_draft_success_with_close():
    """Test saving a draft with close=True deletes the tmp_draft row."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    mail_data = {"subject": "Hello", "body": "Hi"}
    result, status_code = interface.save_draft(account_id="0", mail_data=mail_data, key="abc123", close=True)

    assert status_code == 200
    assert fake_mail.save_draft_args == ("0", mail_data, "abc123", True)


def test_save_draft_module_error():
    """Test error handling when save_draft raises RequestException."""
    fake_mail = FakeModuleMail()
    fake_mail.save_draft = lambda *a, **kw: (_ for _ in ()).throw(
        RequestException("Draft save failed", err.ERROR_MAIL_SAVE_DRAFT_FAILED)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.save_draft(account_id="0", mail_data={})

    assert result["error_code"] == "S000365"
    assert status_code == 500


# ========== Tests for send_mail ==========

def test_send_mail_success_no_key():
    """Test sending a mail without a tmp_draft key."""
    fake_mail = FakeModuleMail()
    fake_outgoing = FakeModuleMailOutgoing()
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    mail_data = {"subject": "Hello", "to": ["bob@example.com"], "body": "Hi"}
    result, status_code = interface.send_mail(account_id="0", mail_data=mail_data)

    assert status_code == 200
    assert result["data"] is None
    assert fake_outgoing.send_mail_args == ("0", mail_data, None)
    assert fake_mail.save_mail_to_folder_args is not None
    assert fake_mail.delete_tmp_draft_args is None  # No key → no cleanup


def test_send_mail_success_with_key():
    """Test sending a mail with a tmp_draft key triggers validation and cleanup."""
    fake_mail = FakeModuleMail()
    fake_outgoing = FakeModuleMailOutgoing()
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    mail_data = {"subject": "Reply", "to": ["bob@example.com"], "body": "Hi"}
    result, status_code = interface.send_mail(account_id="0", mail_data=mail_data, key="abc123")

    assert status_code == 200
    assert fake_mail.validate_tmp_draft_key_args == ("abc123",)
    assert fake_mail.get_headers_from_tmp_draft_args == ("abc123",)
    assert fake_mail.delete_tmp_draft_args == ("abc123", "0")


def test_send_mail_with_key_merges_draft_attachments():
    """Test that attachments from the tmp_draft are merged with mail_data before sending."""
    fake_mail = FakeModuleMail()
    fake_mail.get_attachments_from_tmp_draft_result = [
        {"filename": "draft_attach.pdf", "content_type": "application/pdf", "data": b"bytes"}
    ]
    fake_outgoing = FakeModuleMailOutgoing()
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    mail_data = {"subject": "Hello", "attachments": [{"filename": "existing.txt", "data": b"x"}]}
    interface.send_mail(account_id="0", mail_data=mail_data, key="abc123")

    sent_mail_data = fake_outgoing.send_mail_args[1]
    assert len(sent_mail_data["attachments"]) == 2
    filenames = [a["filename"] for a in sent_mail_data["attachments"]]
    assert "existing.txt" in filenames
    assert "draft_attach.pdf" in filenames


def test_send_mail_invalid_key_returns_error():
    """Test that an invalid tmp_draft key aborts sending."""
    fake_mail = FakeModuleMail()
    fake_mail.validate_tmp_draft_key = lambda key: (_ for _ in ()).throw(
        RequestException("Key not found", err.ERROR_TMP_DRAFT_NOT_FOUND)
    )
    fake_outgoing = FakeModuleMailOutgoing()
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    result, status_code = interface.send_mail(account_id="0", mail_data={}, key="bad-key")

    assert result["error_code"] == "S000370"
    assert status_code == 404
    assert fake_outgoing.send_mail_args is None  # send_mail must NOT have been called


def test_send_mail_smtp_error():
    """Test error handling when SMTP send raises RequestException."""
    fake_mail = FakeModuleMail()
    fake_outgoing = FakeModuleMailOutgoing()
    fake_outgoing.send_mail = lambda *a, **kw: (_ for _ in ()).throw(
        RequestException("SMTP connection failed", err.ERROR_SMTP_CONNECTION_FAILED)
    )
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    result, status_code = interface.send_mail(account_id="0", mail_data={"subject": "Hi"})

    assert result["error_code"] == "S001400"
    assert status_code >= 500


def test_send_mail_save_to_folder_failure_is_non_fatal():
    """Test that a failure to save to Sent folder does not prevent a 200 response."""
    fake_mail = FakeModuleMail()
    fake_mail.save_mail_to_folder = lambda *a: (_ for _ in ()).throw(
        RequestException("Save failed", err.ERROR_MAIL_SAVE_SENT_FAILED)
    )
    fake_outgoing = FakeModuleMailOutgoing()
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    result, status_code = interface.send_mail(account_id="0", mail_data={"subject": "Hi"})

    assert status_code == 200


def test_send_mail_delete_tmp_draft_failure_is_non_fatal():
    """Test that a failure to delete the tmp_draft after send does not prevent a 200 response."""
    fake_mail = FakeModuleMail()
    fake_mail.delete_tmp_draft = lambda *a: (_ for _ in ()).throw(
        RequestException("Delete failed", err.ERROR_TMP_DRAFT_DELETE_FAILED)
    )
    fake_outgoing = FakeModuleMailOutgoing()
    interface = make_interface(fake_mail_module=fake_mail, fake_outgoing_module=fake_outgoing)

    result, status_code = interface.send_mail(account_id="0", mail_data={"subject": "Hi"}, key="abc123")

    assert status_code == 200


# ========== Tests for delete_draft ==========

def test_delete_draft_success():
    """Test deleting a draft and its tmp_draft row."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.delete_draft(account_id="0", key="abc123")

    assert status_code == 200
    assert fake_mail.delete_draft_and_tmp_args == ("0", "abc123")


def test_delete_draft_module_error():
    """Test error handling when delete_draft_and_tmp raises RequestException."""
    fake_mail = FakeModuleMail()
    fake_mail.delete_draft_and_tmp = lambda *a: (_ for _ in ()).throw(
        RequestException("Draft not found", err.ERROR_TMP_DRAFT_NOT_FOUND)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.delete_draft(account_id="0", key="missing-key")

    assert result["error_code"] == "S000370"
    assert status_code == 404


# ========== Tests for list_current_drafts ==========

def test_list_current_drafts_success():
    """Test listing all tmp_draft entries for the current user."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.list_current_drafts()

    assert status_code == 200
    assert result["data"] == [{"key": "abc123", "subject": "Draft 1"}]
    assert fake_mail.list_current_drafts_args == ()


def test_list_current_drafts_module_error():
    """Test error handling when list_current_drafts raises RequestException."""
    fake_mail = FakeModuleMail()
    fake_mail.list_current_drafts = lambda *a: (_ for _ in ()).throw(
        RequestException("DB error", err.ERROR_IMAP_CONNECTION_FAILED)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.list_current_drafts()

    assert result["error_code"] == "S000311"
    assert status_code >= 500


# ========== Tests for upload_attachment ==========

def test_upload_attachment_success_no_key():
    """Test uploading an attachment without an existing tmp_draft key."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.upload_attachment(
        account_id="0", filename="file.pdf", content_type="application/pdf", file_data=b"bytes"
    )

    assert status_code == 200
    assert result["data"]["filename"] == "file.pdf"
    assert fake_mail.upload_attachment_args == ("0", "file.pdf", "application/pdf", b"bytes", None)


def test_upload_attachment_success_with_key():
    """Test uploading an attachment to an existing tmp_draft."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.upload_attachment(
        account_id="0", filename="file.pdf", content_type="application/pdf", file_data=b"bytes", key="abc123"
    )

    assert status_code == 200
    assert fake_mail.upload_attachment_args == ("0", "file.pdf", "application/pdf", b"bytes", "abc123")


def test_upload_attachment_module_error():
    """Test error handling when upload_attachment raises RequestException."""
    fake_mail = FakeModuleMail()
    fake_mail.upload_attachment = lambda *a, **kw: (_ for _ in ()).throw(
        RequestException("Attachment failed", err.ERROR_TMP_DRAFT_ATTACHMENT_FAILED)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.upload_attachment(
        account_id="0", filename="file.pdf", content_type="application/pdf", file_data=b"bytes"
    )

    assert result["error_code"] == "S000377"
    assert status_code == 500


# ========== Tests for delete_attachment ==========

def test_delete_attachment_success():
    """Test removing an attachment from the IMAP draft linked to a key."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.delete_attachment(account_id="0", key="abc123", filename="file.pdf")

    assert status_code == 200
    assert fake_mail.delete_attachment_args == ("0", "abc123", "file.pdf")


def test_delete_attachment_not_found():
    """Test error handling when the attachment to delete does not exist."""
    fake_mail = FakeModuleMail()
    fake_mail.delete_attachment = lambda *a: (_ for _ in ()).throw(
        RequestException("Attachment not found", err.ERROR_TMP_DRAFT_ATTACHMENT_NOT_FOUND)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.delete_attachment(account_id="0", key="abc123", filename="missing.pdf")

    assert result["error_code"] == "S000378"
    assert status_code == 404


def test_delete_attachment_module_error():
    """Test error handling when delete_attachment raises a generic RequestException."""
    fake_mail = FakeModuleMail()
    fake_mail.delete_attachment = lambda *a: (_ for _ in ()).throw(
        RequestException("Delete failed", err.ERROR_TMP_DRAFT_DELETE_ATTACHMENT_FAILED)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.delete_attachment(account_id="0", key="abc123", filename="file.pdf")

    assert result["error_code"] == "S000379"
    assert status_code == 500


# ========== Tests for download_draft_attachment ==========

def test_download_draft_attachment_success():
    """Test downloading an attachment from the IMAP draft linked to a key."""
    fake_mail = FakeModuleMail()
    interface = make_interface(fake_mail_module=fake_mail)

    raw_bytes, content_type = interface.download_draft_attachment(
        account_id="0", key="abc123", filename="file.pdf"
    )

    assert raw_bytes == b"raw bytes"
    assert content_type == "application/pdf"
    assert fake_mail.download_draft_attachment_args == ("0", "abc123", "file.pdf")


def test_download_draft_attachment_not_found():
    """Test error handling when the attachment to download does not exist."""
    fake_mail = FakeModuleMail()
    fake_mail.download_draft_attachment = lambda *a: (_ for _ in ()).throw(
        RequestException("Attachment not found", err.ERROR_TMP_DRAFT_ATTACHMENT_NOT_FOUND)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.download_draft_attachment(
        account_id="0", key="abc123", filename="missing.pdf"
    )

    assert result["error_code"] == "S000378"
    assert status_code == 404


def test_download_draft_attachment_module_error():
    """Test error handling when download_draft_attachment raises a generic RequestException."""
    fake_mail = FakeModuleMail()
    fake_mail.download_draft_attachment = lambda *a: (_ for _ in ()).throw(
        RequestException("Download failed", err.ERROR_IMAP_FAILED)
    )
    interface = make_interface(fake_mail_module=fake_mail)

    result, status_code = interface.download_draft_attachment(
        account_id="0", key="abc123", filename="file.pdf"
    )

    assert result["error_code"] == "S001302"
    assert status_code == 500
