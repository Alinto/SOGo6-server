"""Unit tests for the CardAddressBook model."""
import pytest

from app.module.contact.model.CardAddressBook import CardAddressBook
from app.utils.exceptions import BugException


def _book(**kwargs):
    defaults = dict(user_uid="alice@example.com", name="Personal")
    defaults.update(kwargs)
    return CardAddressBook(**defaults)


def test_apply_update_applies_mutable_fields():
    book = _book(name="Old", description="d", is_default=False)
    book.apply_update({"name": "New", "is_default": True})
    assert book.name == "New"
    assert book.is_default is True


def test_apply_update_ignores_immutable_and_unknown_fields():
    book = _book(key="k1", user_uid="alice@example.com")
    book.apply_update({"key": "hacked", "user_uid": "bob@example.com", "unknown": 1})
    assert book.key == "k1"
    assert book.user_uid == "alice@example.com"


def test_require_id_raises_before_persist():
    with pytest.raises(BugException):
        _ = _book().require_id


def test_require_key_raises_before_persist():
    with pytest.raises(BugException):
        _ = _book().require_key
