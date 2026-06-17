"""Unit tests for the ContactSources factory."""
from unittest.mock import MagicMock, patch

import pytest

from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList
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


def _book(source_type=CardSourceType.LOCAL, key="ab-k", name="Personal"):
    return CardAddressBook(user_uid="u", name=name, key=key, source_type=source_type)


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


def test_search_all_lists_resolves_members_and_book_name():
    sources = _build()
    fake_source = MagicMock()
    fake_source.addressbook = _book(key="ab-k", name="Personal")
    fake_source.get_lists.return_value = [CardList(name="Team", key="l1", addressbook_key="ab-k", members=["c1"])]
    fake_source.get_contact_by_key.return_value = CardContact(display_name="Carol", key="c1")
    sources.get_all = MagicMock(return_value=[fake_source])
    result = sources.search_all_lists("u", search="te")
    assert result[0].addressbook_name == "Personal"
    assert [c.key for c in result[0].member_contacts] == ["c1"]


def test_get_by_key_returns_none_when_absent():
    sources = _build()
    sources._repo_addressbook.find_by_key.return_value = None
    assert sources.get_by_key("u", "ab-k") is None


# ========== get_contacts ==========

def _source_with(contacts, count, book=None):
    source = MagicMock()
    source.addressbook = book or _book()
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


def test_get_contacts_transverse_all_db_uses_single_query():
    # All-DB sources -> one find_by_addressbooks query (no per-book full load / in-memory paging).
    sources = _build()
    db1 = ContactSourceDb(sources._db, _book(key="ab1", name="One"))
    db2 = ContactSourceDb(sources._db, _book(key="ab2", name="Two"))
    sources.get_all = MagicMock(return_value=[db1, db2])
    with patch("app.module.contact.source.ContactSources.RepositoryContact") as repo_cls:
        repo = repo_cls.return_value
        repo.find_by_addressbooks.return_value = [CardContact(display_name="A", addressbook_key="ab1")]
        repo.count_by_addressbooks.return_value = 7
        page, total = sources.get_contacts("u")  # addressbook_key None -> transverse
    assert total == 7 and len(page) == 1
    assert repo.find_by_addressbooks.call_args.args[0] == ["ab1", "ab2"]  # both books, one query


def test_get_contacts_transverse_mixed_sources_merges_in_memory():
    # A non-DB (directory) source forces the in-memory merge fallback.
    sources = _build()
    src1 = _source_with([CardContact(display_name="Zoe"), CardContact(display_name="Bob")], 2)
    src2 = _source_with([CardContact(display_name="Amy")], 1)
    sources.get_all = MagicMock(return_value=[src1, src2])
    page, total = sources.get_contacts("u")
    assert total == 3
    assert [c.display_name for c in page] == ["Amy", "Bob", "Zoe"]


def test_get_contacts_stamps_addressbook_name():
    sources = _build()
    contact = CardContact(display_name="A", addressbook_key="ab-k")
    sources.get_all = MagicMock(return_value=[_source_with([contact], 1, _book(key="ab-k", name="Work"))])
    page, _ = sources.get_contacts("u")
    assert page[0].addressbook_name == "Work"


def test_get_contacts_resolve_ab_false_skips_stamping():
    sources = _build()
    contact = CardContact(display_name="A", addressbook_key="ab-k")
    sources.get_all = MagicMock(return_value=[_source_with([contact], 1, _book(key="ab-k", name="Work"))])
    page, _ = sources.get_contacts("u", resolve_ab=False)
    assert page[0].addressbook_name is None


def test_get_contacts_transverse_paginates():
    sources = _build()
    src = _source_with([CardContact(display_name=name) for name in ("A", "B", "C", "D")], 4)
    sources.get_all = MagicMock(return_value=[src])
    page, total = sources.get_contacts("u", offset=1, limit=2)
    assert total == 4
    assert [c.display_name for c in page] == ["B", "C"]
