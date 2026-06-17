"""Unit tests for CardListAutocompleteSerializerList."""
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.CardListAutocompleteSerializerList import CardListAutocompleteSerializerList

_serializer = CardListAutocompleteSerializerList()


def test_list_suggestion_carries_resolved_members_not_email():
    members = [
        CardContact(display_name="Alice", key="c1", emails=[CardEmail(value="a@x.com")]),
        CardContact(display_name="Bob", key="c2"),  # member without an email
    ]
    lists = [CardList(name="Team", key="l1", addressbook_key="ab1", addressbook_name="Personal",
                      members=["c1", "c2"], member_contacts=members)]
    assert _serializer.serialize(lists) == [
        {"type": "list", "name": "Team", "email": None, "contact_key": None, "list_key": "l1",
         "member_count": 2,
         "members": [
             {"contact_key": "c1", "name": "Alice", "email": "a@x.com"},
             {"contact_key": "c2", "name": "Bob", "email": None},
         ],
         "address_book": {"key": "ab1", "name": "Personal"}},
    ]


def test_list_without_addressbook_has_null_address_book():
    result = _serializer.serialize([CardList(name="Floating", key="l9")])
    assert result[0]["address_book"] is None
    assert result[0]["member_count"] == 0
    assert result[0]["members"] == []
