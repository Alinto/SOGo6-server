"""Unit tests for the address book import deserializers (document -> contacts + lists, members linked)."""
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.serializer.AddressBookContentSerializerLdif import AddressBookContentSerializerLdif
from app.module.contact.serializer.AddressBookContentSerializerVcard import AddressBookContentSerializerVcard
from app.module.contact.serializer.AddressBookContentDeserializerLdif import AddressBookContentDeserializerLdif
from app.module.contact.serializer.AddressBookContentDeserializerVcard import AddressBookContentDeserializerVcard
from app.module.contact.serializer.CardListSerializerVcard4 import CardListSerializerVcard4
from app.module.contact.serializer.CardContactSerializerVcard4 import CardContactSerializerVcard4
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList


VCARD_DOC = (
    "BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Alice\r\nUID:u1\r\nEND:VCARD\r\n"
    "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Bob\r\nUID:u2\r\nEND:VCARD\r\n"
    "BEGIN:VCARD\r\nVERSION:4.0\r\nKIND:group\r\nFN:Team\r\nUID:l1\r\n"
    "MEMBER:urn:uuid:u1\r\nMEMBER:urn:uuid:u2\r\nMEMBER:urn:uuid:ghost\r\nEND:VCARD\r\n"
)


# ========== vCard ==========

def test_vcard_splits_contacts_and_lists():
    content = AddressBookContentDeserializerVcard().deserialize(VCARD_DOC)
    assert [c.display_name for c in content.contacts] == ["Alice", "Bob"]
    assert len(content.lists) == 1 and content.lists[0].name == "Team"


def test_vcard_links_members_to_parsed_contacts_dropping_unknown():
    content = AddressBookContentDeserializerVcard().deserialize(VCARD_DOC)
    linked = content.lists[0].member_contacts
    assert [c.uid for c in linked] == ["u1", "u2"]  # the urn:uuid:ghost member has no contact, dropped


def test_vcard_round_trip_through_export():
    book = AddressBookContent(
        contacts=[CardContact(display_name="Alice", uid="u1"), CardContact(display_name="Bob", uid="u2")],
        lists=[CardList(name="Team", uid="l1", member_contacts=[CardContact(uid="u1")])])
    document = AddressBookContentSerializerVcard(CardContactSerializerVcard4(), CardListSerializerVcard4()).serialize(book)
    back = AddressBookContentDeserializerVcard().deserialize(document)
    assert [c.display_name for c in back.contacts] == ["Alice", "Bob"]
    assert [c.uid for c in back.lists[0].member_contacts] == ["u1"]


# ========== LDIF ==========

def test_ldif_splits_and_links_members_by_cn():
    book = AddressBookContent(
        contacts=[CardContact(display_name="Alice", uid="u1"), CardContact(display_name="Bob", uid="u2")],
        lists=[CardList(name="Team", member_contacts=[CardContact(display_name="Alice", uid="u1")])])
    document = AddressBookContentSerializerLdif().serialize(book)
    back = AddressBookContentDeserializerLdif().deserialize(document)
    assert [c.display_name for c in back.contacts] == ["Alice", "Bob"]
    assert len(back.lists) == 1
    assert [c.display_name for c in back.lists[0].member_contacts] == ["Alice"]
