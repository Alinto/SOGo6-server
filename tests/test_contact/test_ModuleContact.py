"""Unit tests for ModuleContact (address book + contact orchestration)."""
from unittest.mock import MagicMock

import pytest

from app.module.contact.ModuleContact import ModuleContact
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _user(uid="alice@example.com"):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return user


def _book(key="ab-k", is_default=False):
    return CardAddressBook(user_uid="alice@example.com", name="Personal", key=key,
                           is_default=is_default, source_type=CardSourceType.LOCAL)


def _fake_source(book=None):
    source = MagicMock()
    source.addressbook = book or _book()
    return source


def _build_module():
    module = object.__new__(ModuleContact)
    module._db = MagicMock()
    module._cache = None
    module._sources = MagicMock()
    return module


# ========== create_personal_addressbook ==========

def test_create_personal_addressbook_returns_existing_default():
    module = _build_module()
    existing = _fake_source(_book(is_default=True))
    module._sources.get_all.return_value = [existing]
    result = module.create_personal_addressbook("alice@example.com")
    assert result is existing.addressbook
    module._sources.get.assert_not_called()


def test_create_personal_addressbook_creates_when_none():
    module = _build_module()
    module._sources.get_all.return_value = []
    new_source = _fake_source()
    new_source.save_addressbook.side_effect = lambda book: book
    module._sources.get.return_value = new_source
    result = module.create_personal_addressbook("alice@example.com")
    assert result.is_default is True
    assert result.name == "Personal contacts"
    new_source.save_addressbook.assert_called_once()


# ========== address books ==========

def test_get_addressbook_raises_not_found():
    module = _build_module()
    module._sources.get_by_key.return_value = None
    with pytest.raises(RequestException) as exc:
        module.get_addressbook(_user(), "missing")
    assert exc.value.error == err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND


# ========== contacts ==========

def test_create_contact_applies_defaults_and_sets_book_key():
    module = _build_module()
    source = _fake_source(_book(key="ab-k"))
    source.insert_contact.side_effect = lambda contact: contact
    module._sources.get_by_key.return_value = source
    result = module.create_contact(_user(), "ab-k", CardContact(first_name="John", last_name="Doe"))
    assert result.uid
    assert result.display_name == "John Doe"
    assert result.addressbook_key == "ab-k"
    source.insert_contact.assert_called_once()


def test_create_contact_rejects_read_only_source():
    module = _build_module()
    source = _fake_source()
    source.is_writable.return_value = False
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.create_contact(_user(), "ab-k", CardContact(display_name="X"))
    assert exc.value.error == err.ERROR_CONTACT_ADDRESSBOOK_READ_ONLY


def test_get_contact_raises_not_found():
    module = _build_module()
    source = _fake_source()
    source.get_contact_by_key.return_value = None
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.get_contact(_user(), "ab-k", "missing")
    assert exc.value.error == err.ERROR_CONTACT_NOT_FOUND


def test_update_contact_preserves_identity():
    module = _build_module()
    existing = CardContact(db_id=7, key="ct-k", uid="u-1", addressbook_key="ab-k", display_name="Old")
    source = _fake_source(_book(key="ab-k"))
    source.get_contact_by_key.return_value = existing
    module._sources.get_by_key.return_value = source
    update = CardContact(key="hacked", uid="hacked", addressbook_key="other", display_name="New")
    module.update_contact(_user(), "ab-k", "ct-k", update)
    persisted = source.update_contact.call_args.args[0]
    assert persisted.db_id == 7
    assert persisted.key == "ct-k"
    assert persisted.uid == "u-1"
    assert persisted.addressbook_key == "ab-k"
    assert persisted.display_name == "New"


def test_get_contacts_delegates_to_sources_and_returns_page_and_total():
    module = _build_module()
    module._sources.get_contacts.return_value = ([CardContact(display_name="A")], 42)
    contacts, total = module.get_contacts(_user(), "ab-k", search="a", limit=10)
    assert len(contacts) == 1
    assert total == 42
    # addressbook_key threaded through to the aggregator.
    assert module._sources.get_contacts.call_args.kwargs["addressbook_key"] == "ab-k"


def test_get_contacts_transverse_when_no_addressbook_key():
    module = _build_module()
    module._sources.get_contacts.return_value = ([], 0)
    module.get_contacts(_user(), search="joe")
    assert module._sources.get_contacts.call_args.kwargs["addressbook_key"] is None


def test_delete_contact_raises_not_found_when_absent():
    module = _build_module()
    source = _fake_source()
    source.get_contact_by_key.return_value = None
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException):
        module.delete_contact(_user(), "ab-k", "missing")
