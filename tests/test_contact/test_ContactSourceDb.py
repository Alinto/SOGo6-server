"""Unit tests for ContactSourceDb (address book + contact persistence orchestration)."""
from unittest.mock import MagicMock

from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.source.ContactSourceDb import ContactSourceDb
from app.utils.db.Condition import Order


def _book(**kwargs):
    defaults = dict(user_uid="u", name="Personal", key="ab-k", id=1,
                    is_default=False, source_type=CardSourceType.LOCAL, ctag=0)
    defaults.update(kwargs)
    return CardAddressBook(**defaults)


def _build_source(book=None):
    source = object.__new__(ContactSourceDb)
    source._addressbook = book or _book()
    source._repo_addressbook = MagicMock()
    source._repo_contact = MagicMock()
    source._repo_list = MagicMock()
    source._repo_list.find_by_addressbook.return_value = []
    source._repo_list.find_member_keys.return_value = []
    return source


def test_save_addressbook_clears_default_when_default():
    source = _build_source()
    book = _book(is_default=True, id=5)
    source._repo_addressbook.insert.return_value = book
    source.save_addressbook(book)
    source._repo_addressbook.clear_default.assert_called_once_with("u", 5)


def test_save_addressbook_no_clear_when_not_default():
    source = _build_source()
    book = _book(is_default=False, id=5)
    source._repo_addressbook.insert.return_value = book
    source.save_addressbook(book)
    source._repo_addressbook.clear_default.assert_not_called()


def test_delete_addressbook_soft_tombstones_contacts_then_book():
    source = _build_source(_book(key="ab-k", id=1))
    source.delete_addressbook()
    source._repo_contact.delete_all.assert_called_once_with("ab-k", hard_delete=False)
    source._repo_addressbook.delete.assert_called_once_with(1)


def test_delete_addressbook_hard_removes_contacts():
    source = _build_source(_book(key="ab-k", id=1))
    source.delete_addressbook(hard_delete=True)
    source._repo_contact.delete_all.assert_called_once_with("ab-k", hard_delete=True)


def test_insert_contact_bumps_ctag():
    source = _build_source(_book(ctag=3))
    source._repo_contact.insert.side_effect = lambda c: c
    source.insert_contact(CardContact(display_name="X", uid="u", addressbook_key="ab-k"))
    assert source._addressbook.ctag == 4
    source._repo_addressbook.update.assert_called_once()


def test_delete_contact_removes_it_from_all_lists():
    source = _build_source(_book(key="ab-k", ctag=2))
    source.delete_contact("ct-k")
    source._repo_contact.delete_by_key.assert_called_once_with("ab-k", "ct-k")
    source._repo_list.remove_contact_from_lists.assert_called_once_with("ct-k")
    assert source._addressbook.ctag == 3


def test_get_contacts_defaults_sort_to_display_name():
    source = _build_source(_book(key="ab-k"))
    source.get_contacts(search="joe", offset=0, limit=10, sort_by=None)
    # find_by_addressbook(addressbook_key, search, offset, limit, sort_column, order)
    assert source._repo_contact.find_by_addressbook.call_args.args[4] == "display_name"


def test_get_contacts_rejects_unknown_sort_column():
    source = _build_source(_book(key="ab-k"))
    source.get_contacts(sort_by="last_name); DROP TABLE")
    assert source._repo_contact.find_by_addressbook.call_args.args[4] == "display_name"


def test_get_contacts_forwards_valid_sort_and_order():
    source = _build_source(_book(key="ab-k"))
    source.get_contacts(sort_by="last_name", order=Order.DESC)
    assert source._repo_contact.find_by_addressbook.call_args.args[4] == "last_name"
    assert source._repo_contact.find_by_addressbook.call_args.args[5] == Order.DESC


# ========== distribution lists ==========

def test_delete_addressbook_clears_list_members_then_removes_lists():
    source = _build_source(_book(key="ab-k", id=1))
    source._repo_list.find_by_addressbook.return_value = [CardList(name="Team", key="lst-1")]
    source.delete_addressbook()
    source._repo_list.delete_members.assert_called_once_with("lst-1")
    source._repo_list.delete_all.assert_called_once_with("ab-k", hard_delete=False)


def test_get_lists_defaults_sort_to_name():
    source = _build_source(_book(key="ab-k"))
    source.get_lists(sort_by=None)
    assert source._repo_list.find_by_addressbook.call_args.args[4] == "name"


def test_get_lists_rejects_unknown_sort_column():
    source = _build_source(_book(key="ab-k"))
    source.get_lists(sort_by="name); DROP TABLE")
    assert source._repo_list.find_by_addressbook.call_args.args[4] == "name"


def test_get_lists_populates_members():
    source = _build_source(_book(key="ab-k"))
    source._repo_list.find_by_addressbook.return_value = [CardList(name="Team", key="lst-1")]
    source._repo_list.find_member_keys.return_value = ["ct-1", "ct-2"]
    lists = source.get_lists()
    assert lists[0].members == ["ct-1", "ct-2"]


def test_get_list_by_key_populates_members():
    source = _build_source(_book(key="ab-k"))
    source._repo_list.find_by_key.return_value = CardList(name="Team", key="lst-1")
    source._repo_list.find_member_keys.return_value = ["ct-1"]
    result = source.get_list_by_key("lst-1")
    assert result.members == ["ct-1"]


def test_get_list_by_key_returns_none_when_absent():
    source = _build_source(_book(key="ab-k"))
    source._repo_list.find_by_key.return_value = None
    assert source.get_list_by_key("missing") is None
    source._repo_list.find_member_keys.assert_not_called()


def test_insert_list_persists_members_and_bumps_ctag():
    source = _build_source(_book(ctag=3))
    created = CardList(name="Team", key="lst-1")
    source._repo_list.insert.return_value = created
    source._repo_list.find_member_keys.return_value = ["ct-1", "ct-2"]
    result = source.insert_list(CardList(name="Team", members=["ct-1", "ct-2"]))
    source._repo_list.replace_members.assert_called_once_with("lst-1", ["ct-1", "ct-2"])
    assert result.members == ["ct-1", "ct-2"]
    assert source._addressbook.ctag == 4


def test_update_list_replaces_members_and_bumps_ctag():
    source = _build_source(_book(ctag=1))
    source.update_list(CardList(name="Team", key="lst-1", id=7, members=["ct-9"]))
    source._repo_list.replace_members.assert_called_once_with("lst-1", ["ct-9"])
    assert source._addressbook.ctag == 2


def test_delete_list_clears_members_and_bumps_ctag():
    source = _build_source(_book(key="ab-k", ctag=2))
    source.delete_list("lst-1")
    source._repo_list.delete_by_key.assert_called_once_with("ab-k", "lst-1")
    source._repo_list.delete_members.assert_called_once_with("lst-1")
    assert source._addressbook.ctag == 3
