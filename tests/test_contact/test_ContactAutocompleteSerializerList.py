"""Unit tests for ContactAutocompleteSerializerList."""
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.serializer.ContactAutocompleteSerializerList import ContactAutocompleteSerializerList

_serializer = ContactAutocompleteSerializerList()


def test_one_suggestion_per_email_with_provenance():
    contacts = [
        CardContact(display_name="Alice", key="c1", addressbook_key="ab1", addressbook_name="Personal",
                    emails=[CardEmail(value="a@x.com"), CardEmail(value="a2@x.com")]),
        CardContact(display_name="Bob", key="c2", addressbook_key="ab1", addressbook_name="Personal",
                    emails=[CardEmail(value="bob@x.com")]),
    ]
    assert _serializer.serialize(contacts) == [
        {"name": "Alice", "email": "a@x.com", "contact_key": "c1", "address_book": {"key": "ab1", "name": "Personal"}},
        {"name": "Alice", "email": "a2@x.com", "contact_key": "c1", "address_book": {"key": "ab1", "name": "Personal"}},
        {"name": "Bob", "email": "bob@x.com", "contact_key": "c2", "address_book": {"key": "ab1", "name": "Personal"}},
    ]


def test_contact_without_email_yields_no_suggestion():
    assert _serializer.serialize([CardContact(display_name="NoMail")]) == []


def test_contact_without_addressbook_has_null_address_book():
    result = _serializer.serialize([CardContact(display_name="X", key="c1", emails=[CardEmail(value="x@x.com")])])
    assert result == [{"name": "X", "email": "x@x.com", "contact_key": "c1", "address_book": None}]
