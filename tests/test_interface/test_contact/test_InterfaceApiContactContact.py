"""Unit tests for InterfaceApiContactContact - address book and contact CRUD."""
from unittest.mock import MagicMock

from app.interface.contact.InterfaceApiContactContact import InterfaceApiContactContact
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.ContactConst import AUTOCOMPLETE_DEFAULT_LIMIT
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.serializer.AddressBookContentSerializerLdif import AddressBookContentSerializerLdif
from app.module.contact.serializer.AddressBookContentSerializerVcard import AddressBookContentSerializerVcard
from app.module.contact.serializer.CardAddressBookSerializerDict import CardAddressBookSerializerDict
from app.module.contact.serializer.CardAddressBooksSerializerList import CardAddressBooksSerializerList
from app.module.contact.model.enums.ContactExportFormat import ContactExportFormat
from app.module.contact.serializer.CardListSerializerVcard3 import CardListSerializerVcard3
from app.module.contact.serializer.CardListSerializerVcard4 import CardListSerializerVcard4
from app.module.contact.serializer.CardContactSerializerVcard3 import CardContactSerializerVcard3
from app.module.contact.serializer.CardContactSerializerVcard4 import CardContactSerializerVcard4
from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.CardContactAutocompleteSerializerList import CardContactAutocompleteSerializerList
from app.module.contact.serializer.CardListAutocompleteSerializerList import CardListAutocompleteSerializerList
from app.module.contact.serializer.CardListDeserializerDict import CardListDeserializerDict
from app.module.contact.serializer.CardListSerializerDict import CardListSerializerDict
from app.module.contact.serializer.CardListsSerializerList import CardListsSerializerList
from app.module.contact.serializer.CardContactDeserializerDict import CardContactDeserializerDict
from app.module.contact.serializer.CardContactSerializerDict import CardContactSerializerDict
from app.module.contact.serializer.CardContactsSerializerList import CardContactsSerializerList
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs
from app.utils.db.Condition import Order
from app.utils.exceptions import RequestException


def _build_interface():
    inter = object.__new__(InterfaceApiContactContact)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.module = MagicMock()
    inter._addressbook_serializer = CardAddressBookSerializerDict()
    inter._addressbooks_serializer = CardAddressBooksSerializerList()
    inter._contact_serializer = CardContactSerializerDict()
    inter._contacts_serializer = CardContactsSerializerList()
    inter._contact_deserializer = CardContactDeserializerDict()
    inter._autocomplete_serializer = CardContactAutocompleteSerializerList()
    inter._list_autocomplete_serializer = CardListAutocompleteSerializerList()
    inter._list_serializer = CardListSerializerDict()
    inter._lists_serializer = CardListsSerializerList()
    inter._list_deserializer = CardListDeserializerDict()
    inter._user_module_settings = MagicMock(SOGO_D_AUTOCOMPLETION_MIN_LEN=2)
    inter._book_export_serializers = {
        ContactExportFormat.VCARD4: AddressBookContentSerializerVcard(
            CardContactSerializerVcard4(), CardListSerializerVcard4()),
        ContactExportFormat.VCARD3: AddressBookContentSerializerVcard(
            CardContactSerializerVcard3(), CardListSerializerVcard3()),
        ContactExportFormat.LDIF: AddressBookContentSerializerLdif(),
    }
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


# ========== Distribution lists ==========

def test_get_lists_returns_total_count_and_page():
    inter = _build_interface()
    inter.module.get_all_lists.return_value = ([CardList(name="Team", key="l1")], 7)
    total, data, _ = inter.get_lists("ab1", CollectionPaginateArgs(page=1, page_size=20), search="te")
    assert total == 7
    assert [l["key"] for l in data["data"]["lists"]] == ["l1"]


def test_get_lists_translates_pagination_and_sort():
    inter = _build_interface()
    inter.module.get_all_lists.return_value = ([], 0)
    inter.get_lists("ab1", CollectionPaginateArgs(page=2, page_size=10, sort_by="name", sort_order="desc"))
    kwargs = inter.module.get_all_lists.call_args.kwargs
    assert kwargs["offset"] == 10 and kwargs["limit"] == 10
    assert kwargs["sort_by"] == "name" and kwargs["order"] == Order.DESC


def test_get_list_serializes():
    inter = _build_interface()
    inter.module.get_list.return_value = CardList(name="Team", key="l1", members=["c1", "c2"])
    data, _ = inter.get_list("ab1", "l1")
    assert data["data"]["name"] == "Team"
    assert data["data"]["member_count"] == 2


def test_create_list_deserializes_and_returns_201():
    inter = _build_interface()
    inter.module.create_list.side_effect = lambda user, ab_key, card_list: card_list
    _, code = inter.create_list("ab1", {"name": "Team", "members": ["c1"]})
    created = inter.module.create_list.call_args.args[2]
    assert created.name == "Team"
    assert created.members == ["c1"]
    assert code == 201


def test_create_list_missing_name_returns_parse_error():
    inter = _build_interface()
    data, _ = inter.create_list("ab1", {"description": "no name"})
    assert data["error_code"] == err.ERROR_CONTACT_JSON_PARSE_FAILED.c


def test_patch_list_merges_and_preserves_members():
    inter = _build_interface()
    inter.module.get_list.return_value = CardList(id=1, key="l1", uid="u1", addressbook_key="ab1",
                                                  name="Old", members=["c1", "c2"])
    inter.module.update_list.side_effect = lambda user, ab_key, key, card_list: card_list
    inter.patch_list("ab1", "l1", {"name": "New"})
    merged = inter.module.update_list.call_args.args[3]
    assert merged.name == "New"
    assert merged.members == ["c1", "c2"]  # name-only PATCH keeps the membership


def test_delete_list_returns_success_envelope():
    inter = _build_interface()
    data, _ = inter.delete_list("ab1", "l1")
    assert data["data"] is None
    assert data["error_code"] == "S000000"
    inter.module.delete_list.assert_called_once()


def test_autocomplete_returns_one_suggestion_per_email_plus_lists():
    inter = _build_interface()
    inter.module.get_contacts.return_value = (
        [CardContact(display_name="Alice", key="c1", addressbook_key="ab1", addressbook_name="Personal",
                     emails=[CardEmail(value="a@x.com"), CardEmail(value="a2@x.com")])], 1)
    inter.module.search_all_lists.return_value = [
        CardList(name="Team", key="l1", addressbook_key="ab1", addressbook_name="Personal", members=["c1"],
                 member_contacts=[CardContact(display_name="Carol", key="c1", emails=[CardEmail(value="carol@x.com")])])]
    data, _ = inter.autocomplete("ali")
    suggestions = data["data"]["suggestions"]
    # Two contact suggestions (one per email) then one list suggestion.
    assert [s["type"] for s in suggestions] == ["contact", "contact", "list"]
    assert suggestions[2] == {"type": "list", "name": "Team", "email": None, "contact_key": None,
                              "list_key": "l1", "member_count": 1,
                              "members": [{"contact_key": "c1", "name": "Carol", "email": "carol@x.com"}],
                              "address_book": {"key": "ab1", "name": "Personal"}}
    assert inter.module.get_contacts.call_args.kwargs["limit"] == AUTOCOMPLETE_DEFAULT_LIMIT
    assert inter.module.search_all_lists.call_args.kwargs["limit"] == AUTOCOMPLETE_DEFAULT_LIMIT


def test_autocomplete_below_min_length_returns_empty_without_querying():
    inter = _build_interface()
    data, _ = inter.autocomplete("a")
    assert data["data"]["suggestions"] == []
    inter.module.get_contacts.assert_not_called()
    inter.module.search_all_lists.assert_not_called()


# ========== Export ==========

def _book_content():
    return AddressBookContent(
        contacts=[CardContact(display_name="Alice", uid="u1"), CardContact(display_name="Bob", uid="u2")],
        lists=[CardList(name="Team", uid="l1", members=[])],
    )


def test_export_addressbook_defaults_to_vcard3():
    inter = _build_interface()
    inter.module.get_addressbook_content.return_value = _book_content()
    body, code, headers = inter.export_addressbook("k1", "")
    assert code == 200
    assert body.count("BEGIN:VCARD") == 3 and "VERSION:3.0" in body
    assert headers["Content-Type"] == "text/vcard; charset=utf-8; version=3.0"
    assert headers["Content-Disposition"] == 'attachment; filename="addressbook-k1.vcf"'


def test_export_addressbook_vcard4_when_requested():
    inter = _build_interface()
    inter.module.get_addressbook_content.return_value = _book_content()
    body, code, _ = inter.export_addressbook("k1", "text/vcard; version=4.0")
    assert code == 200 and "VERSION:4.0" in body


def test_export_addressbook_ldif_from_accept():
    inter = _build_interface()
    inter.module.get_addressbook_content.return_value = _book_content()
    body, code, headers = inter.export_addressbook("k1", "text/ldif")
    assert code == 200 and body.startswith("version: 1")
    assert headers["Content-Type"] == "text/ldif; charset=utf-8"
    assert headers["Content-Disposition"].endswith('.ldif"')


def test_export_addressbook_unsupported_accept_returns_406():
    inter = _build_interface()
    data, code = inter.export_addressbook("k1", "application/json")
    assert code == err.ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED.h
    assert data["error_code"] == err.ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED.c
    inter.module.get_addressbook_content.assert_not_called()


def test_export_contact_vcard3_from_accept():
    inter = _build_interface()
    inter.module.get_contact.return_value = CardContact(display_name="Alice", uid="u1")
    body, code, headers = inter.export_contact("k1", "u1", "text/vcard; version=3.0")
    assert code == 200 and "VERSION:3.0" in body
    assert headers["Content-Disposition"] == 'attachment; filename="contact-u1.vcf"'


def test_export_list_as_group_card():
    inter = _build_interface()
    inter.module.get_list_for_export.return_value = CardList(
        name="Team", uid="l1", member_contacts=[CardContact(uid="m1")])
    body, code, headers = inter.export_list("k1", "l1", "")
    assert code == 200 and "KIND:group" in body and "MEMBER:urn:uuid:m1" in body
    assert headers["Content-Disposition"] == 'attachment; filename="list-l1.vcf"'
