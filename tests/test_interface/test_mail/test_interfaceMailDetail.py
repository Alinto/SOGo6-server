import pytest
from unittest import mock
from app.interface.mail.InterfaceApiMailDetail import InterfaceApiMailDetail

class FakeModuleMail:
    """
    Fake ModuleMail for testing InterfaceApiMailDetail.
    """
    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.get_mail_detail_args = None
        # --- Résultats configurables par test ---
        self.get_mail_detail_result = {
            "status": True,
            "mail": {"id": "42", "subject": "Test", "from_": "john@example.com"},
            "errors": None
        }

    def get_mail_detail(self, username, password, folder_name, mail_id):
        """
        Fetch the details of a specific mail.
        """
        self.get_mail_detail_args = (username, password, folder_name, mail_id)
        return self.get_mail_detail_result

def patch_module_on_interface(monkeypatch, fake_module):
    """
    Patch the ModuleMail class in the InterfaceApiMailDetail module with a fake module.
    """
    monkeypatch.setattr(
        "app.interface.mail.InterfaceApiMailDetail.ModuleMail",
        lambda *a, **kw: fake_module
    )

def test_given_valid_account_and_mail_when_get_mail_detail_then_return_mail(monkeypatch):
    """
    Test fetching mail details for a valid account and mail.
    """
    # Given
    fake_module = FakeModuleMail()
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailDetail()
    # When
    result = interface.get_mail_detail(account_id=1, folder_name="INBOX", mail_id=42)
    # Then
    assert result["status"] is True
    assert result["mail"]["id"] == "42"
    assert result["mail"]["subject"] == "Test"
    assert fake_module.get_mail_detail_args == ("sogo-tests1@example.org", "sogo", "INBOX", "42") #il faudra peut etre changer cela quand on aura vrai compte?

def test_given_module_error_when_get_mail_detail_then_error(monkeypatch):
    """
    Test handling of errors when fetching mail details.
    """
    # Given
    fake_module = FakeModuleMail()
    fake_module.get_mail_detail_result = {
        "status": False,
        "mail": None,
        "errors": "not found"
    }
    patch_module_on_interface(monkeypatch, fake_module)
    interface = InterfaceApiMailDetail()
    # When
    result = interface.get_mail_detail(account_id=1, folder_name="INBOX", mail_id=999)
    # Then
    assert result["status"] is False
    assert result["mail"] is None
    assert result["errors"] == "not found"
    assert fake_module.get_mail_detail_args == ("sogo-tests1@example.org", "sogo", "INBOX", "999") #il faudra peut etre changer cela quand on aura vrai compte?
