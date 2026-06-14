"""Unit tests for InterfaceApiContactContact - address book and contact CRUD."""
from unittest.mock import MagicMock

from app.interface.contact.InterfaceApiContactContact import InterfaceApiContactContact
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.ContactConst import AUTOCOMPLETE_DEFAULT_LIMIT
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.serializer.AddressBookSerializerDict import AddressBookSerializerDict
from app.module.contact.serializer.AddressBooksSerializerList import AddressBooksSerializerList
from app.module.contact.serializer.ContactAutocompleteSerializerList import ContactAutocompleteSerializerList
from app.module.contact.serializer.ContactDeserializerDict import ContactDeserializerDict
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict
from app.module.contact.serializer.ContactsSerializerList import ContactsSerializerList
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs
from app.utils.db.Condition import Order
from app.utils.exceptions import RequestException


def _build_interface():
    inter = object.__new__(InterfaceApiContactContact)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.module = MagicMock()
    inter._addressbook_serializer = AddressBookSerializerDict()
    inter._addressbooks_serializer = AddressBooksSerializerList()
    inter._contact_serializer = ContactSerializerDict()
    inter._contacts_serializer = ContactsSerializerList()
    inter._contact_deserializer = ContactDeserializerDict()
    inter._autocomplete_serializer = ContactAutocompleteSerializerList()
    inter._user_module_settings = MagicMock(SOGO_D_AUTOCOMPLETION_MIN_LEN=2)
    return inter


def _created_addressbook(inter) -> CardAddressBook:
    return inter.module.create_addressbook.call_args.args[1]


def test_get_all_addressbooks_wraps_list_and_count():
    inter = _build_interface()
    inter.module.get_all_addressbooks.return_value = [
        CardAddressBook(user_uid="alice", name="A", key="k1", source_type=CardSourceType.LOCAL),
        CardAddressBook(user_uid="alice", name="B", key="k2", source_type=CardSourceType.LOCAL),
    ]
    data, _ = inter.get_all_addressbooks()
    assert data["data"]["total_count"] == 2
    assert [b["key"] for b in data["data"]["addressbooks"]] == ["k1", "k2"]


def test_create_addressbook_builds_local_book():
    inter = _build_interface()
    inter.module.create_addressbook.side_effect = lambda user, book: book
    _, code = inter.create_addressbook({"name": "Friends", "description": "d"})
    book = _created_addressbook(inter)
    assert book.user_uid == "alice@example.com"
    assert book.name == "Friends"
    assert book.source_type == CardSourceType.LOCAL
    assert code == 201


def test_update_addressbook_forwards_body_to_module():
    inter = _build_interface()
    inter.module.update_addressbook.return_value = CardAddressBook(
        user_uid="alice", name="Renamed", key="k1", source_type=CardSourceType.LOCAL,
    )
    inter.update_addressbook("k1", {"name": "Renamed"})
    assert inter.module.update_addressbook.call_args.args[1] == "k1"
    assert inter.module.update_addressbook.call_args.args[2] == {"name": "Renamed"}


def test_get_contacts_returns_total_count_as_first_element():
    inter = _build_interface()
    inter.module.get_contacts.return_value = ([CardContact(uid="u1", key="c1", display_name="Alice")], 42)
    total, data, _ = inter.get_contacts("k1", CollectionPaginateArgs(page=1, page_size=20), search="ali")
    assert total == 42  # surfaced through X-Pagination header, not the body
    assert data["data"]["contacts"][0]["display_name"] == "Alice"
    assert "total_count" not in data["data"]


def test_get_contacts_translates_pagination_and_sort():
    inter = _build_interface()
    inter.module.get_contacts.return_value = ([], 0)
    param = CollectionPaginateArgs(page=2, page_size=10, sort_by="last_name", sort_order="desc")
    inter.get_contacts(None, param, search="bob")
    kwargs = inter.module.get_contacts.call_args.kwargs
    assert kwargs == {
        "addressbook_key": None, "search": "bob",
        "offset": 10, "limit": 10, "sort_by": "last_name", "order": Order.DESC,
    }


def test_create_contact_deserializes_and_returns_201():
    inter = _build_interface()
    inter.module.create_contact.side_effect = lambda user, ab_key, contact: contact
    _, code = inter.create_contact("k1", {"display_name": "Carol", "emails": [{"value": "c@x.com"}]})
    created = inter.module.create_contact.call_args.args[2]
    assert created.display_name == "Carol"
    assert created.emails[0].value == "c@x.com"
    assert code == 201


def test_create_contact_invalid_date_returns_parse_error():
    inter = _build_interface()
    data, _ = inter.create_contact("k1", {"display_name": "X", "birthday": "not-a-date"})
    assert data["error_code"] == err.ERROR_CONTACT_JSON_PARSE_FAILED.c


def test_patch_contact_merges_and_updates():
    inter = _build_interface()
    inter.module.get_contact.return_value = CardContact(uid="u1", key="c1", display_name="John", note="old")
    inter.module.update_contact.side_effect = lambda user, ab_key, key, contact: contact
    inter.patch_contact("ab1", "c1", {"note": "new"})
    merged = inter.module.update_contact.call_args.args[3]
    assert merged.note == "new"
    assert merged.display_name == "John"


def test_request_exception_returns_error_envelope():
    inter = _build_interface()
    inter.module.get_addressbook.side_effect = RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
    data, _ = inter.get_addressbook("missing")
    assert data["error_code"] == err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND.c
    assert data["data"] is None


def test_autocomplete_returns_one_suggestion_per_email():
    inter = _build_interface()
    inter.module.get_contacts.return_value = (
        [CardContact(display_name="Alice", key="c1", addressbook_key="ab1", addressbook_name="Personal",
                     emails=[CardEmail(value="a@x.com"), CardEmail(value="a2@x.com")])], 1)
    data, _ = inter.autocomplete("ali")
    assert data["data"]["suggestions"] == [
        {"name": "Alice", "email": "a@x.com", "contact_key": "c1", "address_book": {"key": "ab1", "name": "Personal"}},
        {"name": "Alice", "email": "a2@x.com", "contact_key": "c1", "address_book": {"key": "ab1", "name": "Personal"}}]
    assert inter.module.get_contacts.call_args.kwargs["limit"] == AUTOCOMPLETE_DEFAULT_LIMIT


def test_autocomplete_below_min_length_returns_empty_without_querying():
    inter = _build_interface()
    data, _ = inter.autocomplete("a")
    assert data["data"]["suggestions"] == []
    inter.module.get_contacts.assert_not_called()
