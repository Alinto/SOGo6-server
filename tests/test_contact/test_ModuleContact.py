"""Unit tests for ModuleContact (address book + contact orchestration)."""
from unittest.mock import MagicMock

import pytest

from app.module.contact.ModuleContact import ModuleContact
from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _user(uid="alice@example.com"):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return user


def _book(key="ab-k", is_default=False, user_uid="alice@example.com"):
    return CardAddressBook(user_uid=user_uid, name="Personal", key=key,
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
    module._acl = ContactAclEngine()
    module._file = MagicMock()
    module._file.save_all.side_effect = lambda previous, incoming, max_size, allowed: incoming
    module._file.load_all.side_effect = lambda values: values
    module._file.purge_orphans.return_value = 0
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


def test_create_contact_denied_for_non_owner():
    module = _build_module()
    source = _fake_source(_book(user_uid="someone-else@example.com"))
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.create_contact(_user(), "ab-k", CardContact(display_name="X"))
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


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


def test_update_contact_deletes_dropped_photo_blobs():
    module = _build_module()
    existing = CardContact(db_id=1, key="ct-k", uid="u-1", addressbook_key="ab-k", display_name="X")
    existing.photos = ["sogo:file:old", "https://example.com/keep.png"]
    source = _fake_source(_book(key="ab-k"))
    source.get_contact_by_key.return_value = existing
    module._sources.get_by_key.return_value = source
    update = CardContact(display_name="X")
    update.photos = ["https://example.com/keep.png"]  # the managed ref is dropped, the URI kept
    module.update_contact(_user(), "ab-k", "ct-k", update)
    module._file.delete.assert_called_once_with("sogo:file:old")  # only the dropped blob is reclaimed


def test_update_contact_denied_for_non_owner():
    module = _build_module()
    source = _fake_source(_book(user_uid="someone-else@example.com"))
    source.get_contact_by_key.return_value = CardContact(key="ct-k", uid="u-1", display_name="X")
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.update_contact(_user(), "ab-k", "ct-k", CardContact(display_name="Y"))
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


def test_get_contacts_delegates_to_sources_and_returns_page_and_total():
    module = _build_module()
    module._sources.get_by_key.return_value = _fake_source(_book(key="ab-k"))  # ACL VIEW on the book
    module._sources.get_contacts.return_value = ([CardContact(display_name="A")], 42)
    contacts, total = module.get_contacts(_user(), "ab-k", search="a", limit=10)
    assert len(contacts) == 1
    assert total == 42
    # addressbook_key threaded through to the aggregator.
    assert module._sources.get_contacts.call_args.kwargs["addressbook_key"] == "ab-k"


def test_get_contacts_without_image_resolution_drops_references():
    module = _build_module()
    module._sources.get_by_key.return_value = _fake_source(_book(key="ab-k"))  # ACL VIEW on the book
    contact = CardContact(display_name="A")
    contact.photos = ["sogo:file:abc", "https://example.com/p.png"]
    module._sources.get_contacts.return_value = ([contact], 1)
    module.get_contacts(_user(), "ab-k", resolve_images=False)
    assert contact.photos == ["https://example.com/p.png"]  # managed ref dropped, external URI kept
    module._file.load_all.assert_not_called()             # no blob loaded


def test_get_contact_denied_for_non_owner():
    module = _build_module()
    source = _fake_source(_book(user_uid="someone-else@example.com"))
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.get_contact(_user(), "ab-k", "ct-k")
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED  # ACL VIEW denies a non-owner read


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


# ========== distribution lists ==========

def test_create_list_generates_uid_and_sets_book_key():
    module = _build_module()
    source = _fake_source(_book(key="ab-k"))
    source.insert_list.side_effect = lambda card_list: card_list
    module._sources.get_by_key.return_value = source
    result = module.create_list(_user(), "ab-k", CardList(name="Team", members=["ct-1"]))
    assert result.uid
    assert result.addressbook_key == "ab-k"
    source.insert_list.assert_called_once()


def test_create_list_denied_for_non_owner():
    module = _build_module()
    source = _fake_source(_book(user_uid="someone-else@example.com"))
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.create_list(_user(), "ab-k", CardList(name="X"))
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


def test_create_list_rejects_member_not_in_book():
    module = _build_module()
    source = _fake_source(_book(key="ab-k"))
    source.get_contact_by_key.return_value = None  # member does not resolve in this book
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.create_list(_user(), "ab-k", CardList(name="Team", members=["ghost"]))
    assert exc.value.error == err.ERROR_CONTACT_LIST_MEMBER_INVALID
    source.insert_list.assert_not_called()


def test_update_list_rejects_member_not_in_book():
    module = _build_module()
    source = _fake_source(_book(key="ab-k"))
    source.get_list_by_key.return_value = CardList(id=1, key="lst-k", name="Old")
    source.get_contact_by_key.return_value = None
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.update_list(_user(), "ab-k", "lst-k", CardList(name="New", members=["ghost"]))
    assert exc.value.error == err.ERROR_CONTACT_LIST_MEMBER_INVALID
    source.update_list.assert_not_called()


def test_get_list_raises_not_found():
    module = _build_module()
    source = _fake_source()
    source.get_list_by_key.return_value = None
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.get_list(_user(), "ab-k", "missing")
    assert exc.value.error == err.ERROR_CONTACT_LIST_NOT_FOUND


def test_update_list_preserves_identity():
    module = _build_module()
    existing = CardList(id=7, key="lst-k", uid="u-1", addressbook_key="ab-k", name="Old")
    source = _fake_source(_book(key="ab-k"))
    source.get_list_by_key.return_value = existing
    module._sources.get_by_key.return_value = source
    update = CardList(key="hacked", uid="hacked", addressbook_key="other", name="New", members=["ct-1"])
    module.update_list(_user(), "ab-k", "lst-k", update)
    persisted = source.update_list.call_args.args[0]
    assert persisted.id == 7
    assert persisted.key == "lst-k"
    assert persisted.uid == "u-1"
    assert persisted.addressbook_key == "ab-k"
    assert persisted.name == "New"


def test_delete_list_denied_for_non_owner():
    module = _build_module()
    source = _fake_source(_book(user_uid="someone-else@example.com"))
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException) as exc:
        module.delete_list(_user(), "ab-k", "lst-k")
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


def test_delete_list_raises_not_found_when_absent():
    module = _build_module()
    source = _fake_source()
    source.get_list_by_key.return_value = None
    module._sources.get_by_key.return_value = source
    with pytest.raises(RequestException):
        module.delete_list(_user(), "ab-k", "missing")


def test_get_all_lists_returns_page_and_total():
    module = _build_module()
    source = _fake_source(_book(key="ab-k"))
    source.get_lists.return_value = [CardList(name="Team")]
    source.count_lists.return_value = 3
    module._sources.get_by_key.return_value = source
    lists, total = module.get_all_lists(_user(), "ab-k")
    assert len(lists) == 1
    assert total == 3


def test_search_all_lists_delegates_transverse():
    module = _build_module()
    module._sources.search_all_lists.return_value = [CardList(name="Team")]
    result = module.search_all_lists(_user(), search="te", limit=25)
    assert len(result) == 1
    assert module._sources.search_all_lists.call_args.kwargs["search"] == "te"


# ========== clean ==========

def test_clean_purges_contacts_and_lists():
    module = _build_module()
    module._db.delete_row_in_table.return_value = 5  # each purge_deleted reports 5 rows
    module._db.select_from_table.return_value = []   # no rows, no orphan members
    assert module.clean() == 10  # contacts (5) + lists (5)


def test_clean_purges_orphan_blobs():
    module = _build_module()
    module._db.delete_row_in_table.return_value = 0
    module._db.select_from_table.return_value = []
    module._file.purge_orphans.return_value = 3   # three unreferenced blobs reclaimed
    assert module.clean() == 3
    module._file.purge_orphans.assert_called_once()


# ========== import (upsert by uid) ==========

def _import_source(book=None):
    source = _fake_source(book)
    source.get_contact_by_uid.return_value = None
    source.get_list_by_uid.return_value = None
    source.insert_contact.side_effect = lambda contact: setattr(contact, "key", f"key-{contact.uid}") or contact
    source.insert_list.side_effect = lambda card_list: card_list
    return source


def test_import_addressbook_creates_book_and_imports_content():
    module = _build_module()
    source = _import_source()
    created_book = _book(key="new-ab")
    module.create_addressbook = lambda user, book, user_sources=None: created_book
    module._get_writable_addressbook = lambda *a, **k: source
    c1 = CardContact(display_name="Alice", uid="u1")
    c2 = CardContact(display_name="Bob", uid="u2")
    content = AddressBookContent(contacts=[c1, c2], lists=[CardList(name="Team", uid="l1", member_contacts=[c1, c2])])
    book, result = module.import_addressbook(_user(), content, "Import (2026-06-18)")
    assert book is created_book
    assert (result.contacts_inserted, result.lists_inserted, result.skipped) == (2, 1, 0)
    inserted_list = source.insert_list.call_args.args[0]
    assert inserted_list.members == ["key-u1", "key-u2"]  # member_contacts resolved to the persisted keys


def test_import_contact_updates_when_uid_already_exists():
    module = _build_module()
    source = _import_source()
    existing = CardContact(display_name="Old", uid="u1", key="existing-key", db_id=7)
    source.get_contact_by_uid.side_effect = lambda uid: existing if uid == "u1" else None
    module._get_writable_addressbook = lambda *a, **k: source
    result = module.import_contact(_user(), "ab-k", [CardContact(display_name="New", uid="u1")])
    assert (result.contacts_inserted, result.contacts_updated) == (0, 1)
    source.update_contact.assert_called_once()
    source.insert_contact.assert_not_called()


def test_import_contact_skips_a_failing_entry_without_aborting():
    module = _build_module()
    source = _import_source()

    def _insert(contact):
        if contact.uid == "bad":
            raise RequestException(error=err.ERROR_CONTACT_INSERT_FAILED)
        contact.key = f"key-{contact.uid}"
        return contact

    source.insert_contact.side_effect = _insert
    module._get_writable_addressbook = lambda *a, **k: source
    result = module.import_contact(
        _user(), "ab-k", [CardContact(display_name="Ok", uid="u1"), CardContact(display_name="Bad", uid="bad")])
    assert (result.contacts_inserted, result.skipped) == (1, 1)


def test_import_list_upserts_into_existing_book():
    module = _build_module()
    source = _import_source()
    module._get_writable_addressbook = lambda *a, **k: source
    members = [CardContact(uid="m1", key="key-m1"), CardContact(uid="m2", key="key-m2")]
    result = module.import_list(_user(), "ab-k", [CardList(name="Team", uid="l1", member_contacts=members)])
    assert (result.lists_inserted, result.skipped) == (1, 0)
    assert source.insert_list.call_args.args[0].members == ["key-m1", "key-m2"]


def test_import_list_updates_when_uid_already_exists():
    module = _build_module()
    source = _import_source()
    existing = CardList(id=9, key="existing-key", uid="l1", addressbook_key="ab-k", name="Old")
    source.get_list_by_uid.side_effect = lambda uid: existing if uid == "l1" else None
    module._get_writable_addressbook = lambda *a, **k: source
    result = module.import_list(_user(), "ab-k", [CardList(name="New", uid="l1")])
    assert (result.lists_inserted, result.lists_updated) == (0, 1)
    source.update_list.assert_called_once()
    source.insert_list.assert_not_called()
    persisted = source.update_list.call_args.args[0]
    assert (persisted.id, persisted.key, persisted.uid) == (9, "existing-key", "l1")  # identity from existing, not document


def test_import_list_skips_a_failing_entry_without_aborting():
    module = _build_module()
    source = _import_source()

    def _insert(card_list):
        if card_list.uid == "bad":
            raise RequestException(error=err.ERROR_CONTACT_LIST_INSERT_FAILED)
        return card_list

    source.insert_list.side_effect = _insert
    module._get_writable_addressbook = lambda *a, **k: source
    result = module.import_list(
        _user(), "ab-k", [CardList(name="Ok", uid="l1"), CardList(name="Bad", uid="bad")])
    assert (result.lists_inserted, result.skipped) == (1, 1)
