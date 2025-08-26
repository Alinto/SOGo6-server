import pytest
from unittest import mock
from app.interface.mail.InterfaceApiMailAccount import InterfaceApiMailAccount

class FakeModuleMail:
    """
    Fake ModuleMail for testing InterfaceApiMailAccount.
    """
    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.get_folder_list_args = None
        self.create_folder_args = None
        # --- Résultats configurables par test ---
        self.get_folder_list_result = {"status": True, "folders": [{"name": "INBOX"}], "errors": None}
        self.create_folder_result = (True, "OK")

    def get_folder_list(self, username, password):
        """
        Fetch the list of folders for the given user.
        """
        self.get_folder_list_args = (username, password)
        return self.get_folder_list_result

    def create_folder(self, username, password, folder_name):
        """
        Create a new folder for the given user.
        """
        self.create_folder_args = (username, password, folder_name)
        return self.create_folder_result

def patch_module_on_interface(monkeypatch, fake_module):
    """
    Patch the ModuleMail class in the InterfaceApiMailAccount module with a fake module.
    """
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailAccount.ModuleMail",
        lambda *a, **kw: fake_module
    )

def test_given_valid_account_when_get_folder_list_then_return_folders(monkeypatch):
    """
    Test fetching folder list for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailAccount()
    # When
    result = interface.get_folder_list(account_id=1)
    # Then
    assert result["status"] is True
    assert result["folders"] == [{"name": "INBOX"}]
    assert result["errors"] is None
    # Vérifie les bons identifiants transmis
    assert fake_module.get_folder_list_args == ("sogo-tests1@example.org", "sogo")  #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_get_folder_list_then_error(monkeypatch):
    """
    Test handling of errors when fetching folder list.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.get_folder_list_result = {"status": False, "folders": [], "errors": "IMAP error"}
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailAccount()
    # When
    result = interface.get_folder_list(account_id=1)
    # Then
    assert result["status"] is False
    assert result["folders"] == []
    assert result["errors"] == "IMAP error"

def test_given_valid_account_when_create_folder_then_success(monkeypatch):
    """
    Test creating a folder for a valid account.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.create_folder_result = (True, "OK")
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailAccount()
    # When
    result = interface.create_folder(account_id=1, folder_name="Archive")
    # Then
    assert result["status"] is True
    assert result["errors"] == "OK"
    # Vérifie les bons paramètres transmis
    assert fake_module.create_folder_args == ("sogo-tests1@example.org", "sogo", "Archive") #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_create_folder_then_error(monkeypatch):
    """
    Test handling of errors when creating a folder.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.create_folder_result = (False, "fail to create folder")
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailAccount()
    # When
    result = interface.create_folder(account_id=1, folder_name="Archive")
    # Then
    assert result["status"] is False
    assert result["errors"] == "fail to create folder"
