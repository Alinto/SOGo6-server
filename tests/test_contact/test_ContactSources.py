"""Unit tests for the ContactSources factory."""
from unittest.mock import MagicMock

import pytest

from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.source.ContactSourceDb import ContactSourceDb
from app.module.contact.source.ContactSources import ContactSources
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _build():
    sources = object.__new__(ContactSources)
    sources._db = MagicMock()
    sources._repo_addressbook = MagicMock()
    return sources


def _book(source_type=CardSourceType.LOCAL):
    return CardAddressBook(user_uid="u", name="Personal", key="ab-k", source_type=source_type)


def test_get_local_returns_db_source():
    source = _build().get(_book(CardSourceType.LOCAL))
    assert isinstance(source, ContactSourceDb)


def test_get_unknown_source_type_raises():
    with pytest.raises(RequestException) as exc:
        _build().get(_book(CardSourceType.CARDDAV))
    assert exc.value.error == err.ERROR_CONTACT_ADDRESSBOOK_NOT_SUPPORTED


def test_get_by_key_returns_source_when_found():
    sources = _build()
    sources._repo_addressbook.find_by_key.return_value = _book()
    assert sources.get_by_key("u", "ab-k") is not None


def test_get_by_key_returns_none_when_absent():
    sources = _build()
    sources._repo_addressbook.find_by_key.return_value = None
    assert sources.get_by_key("u", "ab-k") is None


# ========== get_contacts ==========

def _source_with(contacts, count):
    source = MagicMock()
    source.get_contacts.return_value = contacts
    source.count_contacts.return_value = count
    return source


def test_get_contacts_scoped_to_one_book():
    sources = _build()
    sources.get_by_key = MagicMock(return_value=_source_with([CardContact(display_name="A")], 1))
    page, total = sources.get_contacts("u", addressbook_key="ab-k")
    assert len(page) == 1
    assert total == 1


def test_get_contacts_scoped_unknown_book_raises():
    sources = _build()
    sources.get_by_key = MagicMock(return_value=None)
    with pytest.raises(RequestException) as exc:
        sources.get_contacts("u", addressbook_key="missing")
    assert exc.value.error == err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND


def test_get_contacts_transverse_merges_and_sorts():
    sources = _build()
    src1 = _source_with([CardContact(display_name="Zoe"), CardContact(display_name="Bob")], 2)
    src2 = _source_with([CardContact(display_name="Amy")], 1)
    sources.get_all = MagicMock(return_value=[src1, src2])
    page, total = sources.get_contacts("u")  # addressbook_key None -> transverse
    assert total == 3
    assert [c.display_name for c in page] == ["Amy", "Bob", "Zoe"]


def test_get_contacts_transverse_paginates():
    sources = _build()
    src = _source_with([CardContact(display_name=name) for name in ("A", "B", "C", "D")], 4)
    sources.get_all = MagicMock(return_value=[src])
    page, total = sources.get_contacts("u", offset=1, limit=2)
    assert total == 4
    assert [c.display_name for c in page] == ["B", "C"]
