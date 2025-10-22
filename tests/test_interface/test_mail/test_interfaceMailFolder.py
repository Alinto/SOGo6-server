import pytest
from unittest import mock
from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder

class FakeModuleMail:
    """
    Fake ModuleMail for testing InterfaceApiMailFolder.
    """
    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.get_folder_mails_args = None
        self.expunge_mailbox_args = None
        self.delete_folder_args = None
        self.delete_all_mail_in_folder_args = None
        self.delete_mail_by_id_calls = []
        self.move_mail_calls = []

        # --- Résultats configurables par test ---
        self.get_folder_mails_result = {"status": True, "mails": [{"id": "1"}], "errors": None}
        self.expunge_mailbox_result = (True, "OK")
        self.delete_folder_result = (True, "OK")
        self.delete_all_mail_in_folder_result = (True, "mails marked as deleted")
        self.delete_mail_by_id_results = []
        self.move_mail_results = []

    def get_folder_mails(self, username, password, folder_name, page=1, per_page=20):
        """
        Fetch the list of mails in a specific folder.
        """
        self.get_folder_mails_args = (username, password, folder_name, page, per_page)
        return self.get_folder_mails_result

    def expunge_mailbox(self, username, password, folder_name):
        """
        Expunge the mailbox by removing all deleted mails.
        """
        self.expunge_mailbox_args = (username, password, folder_name)
        return self.expunge_mailbox_result

    def delete_folder(self, username, password, folder_name):
        """
        Delete a specific folder.
        """
        self.delete_folder_args = (username, password, folder_name)
        return self.delete_folder_result

    def delete_all_mail_in_folder(self, username, password, folder_name, before_date):
        """
        Delete all mails in a specific folder before a certain date.
        """
        self.delete_all_mail_in_folder_args = (username, password, folder_name, before_date)
        return self.delete_all_mail_in_folder_result

    def delete_mail_by_id(self, username, password, folder_name, mail_id):
        """
        Delete a specific mail by its ID.
        """
        self.delete_mail_by_id_calls.append((username, password, folder_name, mail_id))
        # Retourne le prochain résultat dans la liste (ou True, "OK" par défaut)
        return self.delete_mail_by_id_results.pop(0) if self.delete_mail_by_id_results else (True, "OK")

    def move_mail(self, username, password, from_folder_name, mail_id, to_folder_name):
        """
        Move a specific mail to another folder.
        """
        self.move_mail_calls.append((username, password, from_folder_name, mail_id, to_folder_name))
        # Retourne le prochain résultat dans la liste (ou True, "OK" par défaut)
        return self.move_mail_results.pop(0) if self.move_mail_results else (True, "OK")

def patch_module_on_interface(monkeypatch, fake_module):
    """
    Patch the ModuleMail class in the InterfaceApiMailFolder module with a fake module.
    """
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailFolder.ModuleMail",
        lambda *a, **kw: fake_module
    )

def test_given_valid_account_when_get_mail_list_then_success(monkeypatch):
    """
    Test fetching mail list for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.get_mail_list(account_id=1, folder_name="INBOX", page=2, per_page=10)
    # Then
    assert result["status"] is True
    assert result["mails"] == [{"id": "1"}]
    assert result["errors"] is None
    assert fake_module.get_folder_mails_args == ("sogo-tests1@example.org", "sogo", "INBOX", 2, 10) #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_get_mail_list_then_error(monkeypatch):
    """
    Test handling of errors when fetching mail list.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.get_folder_mails_result = {"status": False, "mails": [], "errors": "fail"}
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.get_mail_list(account_id=1, folder_name="INBOX")
    # Then
    assert result["status"] is False
    assert not result["mails"]
    assert result["errors"] == "fail"

def test_given_valid_account_when_expunge_folder_then_success(monkeypatch):
    """
    Test expunging a folder for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.expunge_folder(account_id=1, folder_name="INBOX")
    # Then
    assert result["status"] is True
    assert result["errors"] == "OK"
    assert fake_module.expunge_mailbox_args == ("sogo-tests1@example.org", "sogo", "INBOX") #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_expunge_folder_then_error(monkeypatch):
    """
    Test handling of errors when expunging a folder.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.expunge_mailbox_result = (False, "expunge failed")
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.expunge_folder(account_id=1, folder_name="INBOX")
    # Then
    assert result["status"] is False
    assert result["errors"] == "expunge failed"

def test_given_valid_account_when_delete_folder_then_success(monkeypatch):
    """
    Test deleting a folder for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.delete_folder(account_id=1, folder_name="Archive")
    # Then
    assert result["status"] is True
    assert result["errors"] == "OK"
    assert fake_module.delete_folder_args == ("sogo-tests1@example.org", "sogo", "Archive") #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_delete_folder_then_error(monkeypatch):
    """
    Test handling of errors when deleting a folder.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.delete_folder_result = (False, "cannot delete")
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.delete_folder(account_id=1, folder_name="Archive")
    # Then
    assert result["status"] is False
    assert result["errors"] == "cannot delete"

def test_given_valid_account_when_delete_all_mail_in_folder_then_success(monkeypatch):
    """
    Test deleting all mails in a folder for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.delete_all_mail_in_folder_result = (True, "7 mails marked as deleted")
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.delete_all_mail_in_folder(account_id=1, folder_name="INBOX", before_date="2024-01-01")
    # Then
    assert result["status"] is True
    assert result["errors"] == "7 mails marked as deleted"
    assert fake_module.delete_all_mail_in_folder_args == ("sogo-tests1@example.org", "sogo", "INBOX", "2024-01-01") #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_delete_all_mail_in_folder_then_error(monkeypatch):
    """
    Test handling of errors when deleting all mails in a folder.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.delete_all_mail_in_folder_result = (False, "fail delete all")
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.delete_all_mail_in_folder(account_id=1, folder_name="INBOX", before_date=None)
    # Then
    assert result["status"] is False
    assert result["errors"] == "fail delete all"

def test_given_valid_account_when_delete_mails_then_success(monkeypatch):
    """
    Test deleting multiple mails for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.delete_mail_by_id_results = [
        (True, "OK"),
        (True, "OK"),
        (True, "OK"),
    ]
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.delete_mails(account_id=1, folder_name="INBOX", mail_ids=[1,2,3])
    # Then
    assert result["status"] is True
    assert result["deleted_ids"] == [1,2,3]
    assert not result["failed_ids"]
    assert result["errors"] == []
    # Vérifie les bons appels
    assert fake_module.delete_mail_by_id_calls == [
        ("sogo-tests1@example.org", "sogo", "INBOX", "1"),
        ("sogo-tests1@example.org", "sogo", "INBOX", "2"),
        ("sogo-tests1@example.org", "sogo", "INBOX", "3"),
    ]

def test_given_partial_errors_when_delete_mails_then_return_failed(monkeypatch):
    """
    Test handling of partial errors when deleting multiple mails.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.delete_mail_by_id_results = [
        (True, "OK"),
        (False, "not found"),
        (False, "already deleted"),
    ]
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.delete_mails(account_id=1, folder_name="INBOX", mail_ids=[1,2,3])
    # Then
    assert result["status"] is False
    assert result["deleted_ids"] == [1]
    assert result["failed_ids"] == [
        {"id": 2, "error": "not found"},
        {"id": 3, "error": "already deleted"},
    ]
    assert result["errors"] == ["not found", "already deleted"]

def test_given_valid_account_when_move_mails_then_success(monkeypatch):
    """
    Test moving multiple mails for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.move_mail_results = [
        (True, "OK"),
        (True, "OK"),
    ]
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.move_mails(account_id=1, from_folder_name="INBOX", mail_ids=[11, 22], to_folder_name="Sent")
    # Then
    assert result["status"] is True
    assert result["moved_ids"] == [11, 22]
    assert not result["failed_ids"]
    assert result["errors"] == []
    # Vérifie les bons appels
    assert fake_module.move_mail_calls == [
        ("sogo-tests1@example.org", "sogo", "INBOX", "11", "Sent"),
        ("sogo-tests1@example.org", "sogo", "INBOX", "22", "Sent"),
    ]

def test_given_partial_errors_when_move_mails_then_return_failed(monkeypatch):
    """
    Test handling of partial errors when moving multiple mails.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.move_mail_results = [
        (False, "forbidden"),
        (True, "OK"),
    ]
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailFolder()
    # When
    result = interface.move_mails(account_id=1, from_folder_name="INBOX", mail_ids=[1, 2], to_folder_name="Trash")
    # Then
    assert result["status"] is False
    assert result["moved_ids"] == [2]
    assert result["failed_ids"] == [{"id": 1, "error": "forbidden"}]
    assert result["errors"] == ["forbidden"]
