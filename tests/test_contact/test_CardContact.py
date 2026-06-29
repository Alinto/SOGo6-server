"""Unit tests for the CardContact model."""
import pytest

from app.module.contact.model.CardContact import CardContact
from app.utils import errors as err
from app.utils.exceptions import BugException, RequestException


def _contact(**kwargs):
    return CardContact(**kwargs)


# ========== apply_defaults ==========

def test_apply_defaults_generates_uid():
    contact = _contact(display_name="Alice")
    contact.apply_defaults()
    assert contact.uid


def test_apply_defaults_keeps_explicit_uid():
    contact = _contact(uid="fixed-uid", display_name="Alice")
    contact.apply_defaults()
    assert contact.uid == "fixed-uid"


def test_apply_defaults_derives_display_name_from_name():
    contact = _contact(first_name="John", middle_name="A", last_name="Doe")
    contact.apply_defaults()
    assert contact.display_name == "John A Doe"


def test_apply_defaults_display_name_falls_back_to_organization():
    contact = _contact(organization="Tech Corp")
    contact.apply_defaults()
    assert contact.display_name == "Tech Corp"


def test_apply_defaults_display_name_falls_back_to_nickname():
    contact = _contact(nickname="Johnny")
    contact.apply_defaults()
    assert contact.display_name == "Johnny"


def test_apply_defaults_keeps_explicit_display_name():
    contact = _contact(first_name="John", last_name="Doe", display_name="Custom Name")
    contact.apply_defaults()
    assert contact.display_name == "Custom Name"


# ========== validate ==========

def test_validate_ok():
    contact = _contact(display_name="Alice")
    contact.validate()


def test_validate_rejects_missing_display_name():
    contact = _contact()
    with pytest.raises(RequestException) as exc_info:
        contact.validate()
    assert exc_info.value.error == err.ERROR_CONTACT_DISPLAY_NAME_REQUIRED


# ========== require_* ==========

def test_require_uid_raises_before_defaults():
    with pytest.raises(BugException):
        _ = _contact().require_uid


def test_require_key_raises_before_persist():
    with pytest.raises(BugException):
        _ = _contact(uid="u").require_key
