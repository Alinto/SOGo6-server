"""Unit tests for AddressBookSerializerDict and the list serializers."""
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.serializer.AddressBookSerializerDict import AddressBookSerializerDict
from app.module.contact.serializer.AddressBooksSerializerList import AddressBooksSerializerList
from app.module.contact.serializer.ContactsSerializerList import ContactsSerializerList

_serializer = AddressBookSerializerDict()


def test_serialize_addressbook():
    book = CardAddressBook(
        user_uid="alice", name="Personal", key="ab1", description="my book",
        is_default=True, source_type=CardSourceType.LOCAL, ctag=7,
    )
    assert _serializer.serialize(book) == {
        "key": "ab1",
        "name": "Personal",
        "description": "my book",
        "is_default": True,
        "source_type": "local",
        "ctag": 7,
    }


def test_addressbooks_list_serializer():
    books = [
        CardAddressBook(user_uid="alice", name="A", key="k1", source_type=CardSourceType.LOCAL),
        CardAddressBook(user_uid="alice", name="B", key="k2", source_type=CardSourceType.LOCAL),
    ]
    result = AddressBooksSerializerList().serialize(books)
    assert [b["key"] for b in result] == ["k1", "k2"]


def test_contacts_list_serializer():
    contacts = [
        CardContact(uid="u1", key="c1", display_name="Alice"),
        CardContact(uid="u2", key="c2", display_name="Bob"),
    ]
    result = ContactsSerializerList().serialize(contacts)
    assert [c["display_name"] for c in result] == ["Alice", "Bob"]
