# pylint: disable=invalid-sequence-index
from app.interface.mail.InterfaceApiMailMail import InterfaceApiMailMail
from app.utils.exceptions import RequestException
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


class InterfaceApiMailMailWithInjectedConf(InterfaceApiMailMail):
    """Subclass of InterfaceApiMailMail that allows injecting a mail_module directly for testing."""
    def __init__(self, mail_module):
        """Initialize with an injected mail_module for testing.
        
        Does not call the parent __init__ to avoid requiring all the parameters it needs.
        The mail_module is set directly so tests can inject a fake/mock module.
        """
        self.mail_module = mail_module  # noqa: SLF001


class FakeModuleMail:
    """
    Fake ModuleMail for testing InterfaceApiMailMail.
    All methods mirror the new ModuleMail signature where account_id is the first argument.
    """
    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.get_folder_mails_args = None
        self.get_mail_detail_args = None
        self.delete_mails_args = None
        self.get_mail_raw_args = None
        self.reply_mail_args = None
        self.forward_mail_args = None
        self.perform_mail_action_args = None

        # --- Résultats configurables par test ---
        self.get_folder_mails_result = ([{"uid": 1, "subject": "Test"}], 100)
        self.get_mail_detail_result = {
            "uid": 42,
            "subject": "Test Subject",
            "from": "john@example.com",
            "body": "Test body"
        }
        self.get_mail_raw_result = {"raw": "Raw email content"}
        self.reply_mail_result = {"reply": "Reply draft created"}
        self.forward_mail_result = {"forward": "Forward draft created"}
        self.perform_mail_action_result = {"action": "tag", "mail_uid": 42, "tags_added": ["Important"]}

    def get_folder_mails(self, account_id, folder_name, collection_param):
        """Fetch a list of mails from a folder."""
        self.get_folder_mails_args = (account_id, folder_name, collection_param.first_item, collection_param.last_item)
        return self.get_folder_mails_result

    def get_mail_detail(self, account_id, folder_name, mail_uid):
        """Fetch the details of a specific mail."""
        self.get_mail_detail_args = (account_id, folder_name, mail_uid)
        return self.get_mail_detail_result

    def delete_mails(self, account_id, folder_name, mail_uid):
        """Delete a specific mail."""
        self.delete_mails_args = (account_id, folder_name, mail_uid)

    def get_mail_raw(self, account_id, folder_name, mail_uid):
        """Get raw mail content."""
        self.get_mail_raw_args = (account_id, folder_name, mail_uid)
        return self.get_mail_raw_result

    def reply_mail(self, account_id, folder_name, mail_uid):
        """Reply to a mail."""
        self.reply_mail_args = (account_id, folder_name, mail_uid)
        return self.reply_mail_result

    def forward_mail(self, account_id, folder_name, mail_uid):
        """Forward a mail."""
        self.forward_mail_args = (account_id, folder_name, mail_uid)
        return self.forward_mail_result

    def perform_mail_action(self, account_id, folder_name, mail_uid, action_data):
        """Perform an action on a mail."""
        self.perform_mail_action_args = (account_id, folder_name, mail_uid, action_data)
        return self.perform_mail_action_result


def make_interface(fake_module):
    """
    Create an InterfaceApiMailMailWithInjectedConf with the given fake module.
    """
    return InterfaceApiMailMailWithInjectedConf(fake_module)

# ========== Tests for get_mail_list ==========

def test_get_mail_list_success():
    """Test fetching mail list for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(fake_module)

    total, result, status_code = interface.get_mail_list(account_id=0, folder_name="INBOX", collection_param=CollectionPaginateArgs(page=1, page_size=11))

    assert status_code == 200
    assert total == 100
    assert result["data"] == [{"uid": 1, "subject": "Test"}]
    assert fake_module.get_folder_mails_args == (0, "INBOX", 0, 10)

def test_get_mail_list_module_exception():
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleMail()
    fake_module.get_folder_mails = lambda *args: (_ for _ in ()).throw(RequestException("Connection failed", err.ERROR_IMAP_CONNECTION_FAILED))
    interface = make_interface(fake_module)

    total, result, status_code = interface.get_mail_list(account_id=0, folder_name="INBOX", collection_param=CollectionPaginateArgs(page=1, page_size=11))

    assert result["error_code"] == "S000311"
    assert status_code >= 500
    assert total == 0

# ========== Tests for get_mail_detail ==========

def test_get_mail_detail_success():
    """Test fetching mail details for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(fake_module)

    result, status_code = interface.get_mail_detail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["uid"] == 42
    assert result["data"]["subject"] == "Test Subject"
    assert fake_module.get_mail_detail_args == (0, "INBOX", 42)

def test_get_mail_detail_module_error():
    """Test error handling when mail detail fetch fails."""
    fake_module = FakeModuleMail()
    fake_module.get_mail_detail = lambda *args: (_ for _ in ()).throw(RequestException("Mail not found", err.ERROR_MAIL_UID_NOT_FOUND))
    interface = make_interface(fake_module)

    result, status_code = interface.get_mail_detail(account_id=0, folder_name="INBOX", mail_uid=999)

    assert result["error_code"] == "S000303"
    assert status_code == 404

# ========== Tests for delete_mail ==========

def test_delete_mail_success():
    """Test deleting a mail for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(fake_module)

    result, status_code = interface.delete_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result == ""
    assert status_code == 204
    assert fake_module.delete_mails_args == (0, "INBOX", 42)

def test_delete_mail_module_error():
    """Test error handling when mail deletion fails."""
    fake_module = FakeModuleMail()
    fake_module.delete_mails = lambda *args: (_ for _ in ()).throw(RequestException("Cannot delete", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(fake_module)

    result, status_code = interface.delete_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 400
    assert result["error_code"] == "S000300"

# ========== Tests for get_mail_raw ==========

def test_get_mail_raw_success():
    """Test fetching raw mail content for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(fake_module)

    result, status_code = interface.get_mail_raw(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["raw"] == "Raw email content"
    assert fake_module.get_mail_raw_args == (0, "INBOX", 42)

def test_get_mail_raw_module_error():
    """Test error handling when raw mail fetch fails."""
    fake_module = FakeModuleMail()
    fake_module.get_mail_raw = lambda *args: (_ for _ in ()).throw(RequestException("Cannot fetch raw", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(fake_module)

    result, status_code = interface.get_mail_raw(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result["error_code"] == "S000300"
    assert status_code == 400

# ========== Tests for reply_mail ==========

def test_reply_mail_success():
    """Test replying to a mail for a valid account."""
    fake_module = FakeModuleMail()
    interface = make_interface(fake_module)

    result, status_code = interface.reply_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert status_code == 200
    assert result["data"]["reply"] == "Reply draft created"
    assert fake_module.reply_mail_args == (0, "INBOX", 42)


def test_reply_mail_module_error():
    """Test error handling when replying to mail fails."""
    fake_module = FakeModuleMail()
    fake_module.reply_mail = lambda *args: (_ for _ in ()).throw(RequestException("Cannot reply", err.ERROR_VALIDATION_ERROR))
    interface = make_interface(fake_module)

    result, status_code = interface.reply_mail(account_id=0, folder_name="INBOX", mail_uid=42)

    assert result["error_code"] == "S000300"
    assert status_code == 400


# ========== Tests for mail_action ==========

def test_mail_action_tag_success():
    """Test tagging a mail for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action_result = {"action": "tag", "mail_uid": 42, "tags_added": ["Important"]}
    interface = make_interface(fake_module)

    action_data = {"action": "tag", "data": ["Important"]}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 200
    assert result["data"]["action"] == "tag"
    assert result["data"]["mail_uid"] == 42
    assert result["data"]["tags_added"] == ["Important"]
    assert fake_module.perform_mail_action_args == (0, "INBOX", 42, action_data)


def test_mail_action_untag_success():
    """Test untagging a mail for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action_result = {"action": "untag", "mail_uid": 42, "tags_removed": ["Important"]}
    interface = make_interface(fake_module)

    action_data = {"action": "untag", "data": ["Important"]}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 200
    assert result["data"]["action"] == "untag"
    assert result["data"]["tags_removed"] == ["Important"]


def test_mail_action_move_success():
    """Test moving a mail for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action_result = {"action": "move", "mail_uid": 42, "from_folder": "INBOX", "to_folder": "Archive"}
    interface = make_interface(fake_module)

    action_data = {"action": "move", "data": "Archive"}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 200
    assert result["data"]["action"] == "move"
    assert result["data"]["to_folder"] == "Archive"


def test_mail_action_spam_success():
    """Test marking a mail as spam for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action_result = {"action": "spam", "mail_uid": 42, "moved_to": "Junk"}
    interface = make_interface(fake_module)

    action_data = {"action": "spam"}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 200
    assert result["data"]["action"] == "spam"
    assert result["data"]["moved_to"] == "Junk"


def test_mail_action_ham_success():
    """Test marking a mail as ham for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action_result = {"action": "ham", "mail_uid": 42, "moved_to": "INBOX"}
    interface = make_interface(fake_module)

    action_data = {"action": "ham"}
    result, status_code = interface.mail_action(account_id=0, folder_name="Junk", mail_uid=42, action_data=action_data)

    assert status_code == 200
    assert result["data"]["action"] == "ham"
    assert result["data"]["moved_to"] == "INBOX"


def test_mail_action_copy_success():
    """Test copying a mail for a valid account."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action_result = {"action": "copy", "mail_uid": 42, "from_folder": "INBOX", "to_folder": "Archive"}
    interface = make_interface(fake_module)

    action_data = {"action": "copy", "data": "Archive"}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 200
    assert result["data"]["action"] == "copy"
    assert result["data"]["to_folder"] == "Archive"


def test_mail_action_invalid_action():
    """Test error handling for invalid action."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action = lambda *args: (_ for _ in ()).throw(
        RequestException("Invalid action: unknown", err.ERROR_INVALID_ACTION)
    )
    interface = make_interface(fake_module)

    action_data = {"action": "unknown"}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 400
    assert result["error_code"] == "S000309"


def test_mail_action_module_error():
    """Test error handling when module raises RequestException."""
    fake_module = FakeModuleMail()
    fake_module.perform_mail_action = lambda *args: (_ for _ in ()).throw(
        RequestException("Action failed", err.ERROR_VALIDATION_ERROR)
    )
    interface = make_interface(fake_module)

    action_data = {"action": "tag", "data": ["Important"]}
    result, status_code = interface.mail_action(account_id=0, folder_name="INBOX", mail_uid=42, action_data=action_data)

    assert status_code == 400
    assert result["error_code"] == "S000300"
