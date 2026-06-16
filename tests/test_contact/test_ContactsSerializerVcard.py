"""Unit tests for the multi-card vCard serializers and the distribution-list vCard serializers."""
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.ContactListDeserializerVcard import ContactListDeserializerVcard
from app.module.contact.serializer.ContactListSerializerVcard3 import ContactListSerializerVcard3
from app.module.contact.serializer.ContactListSerializerVcard4 import ContactListSerializerVcard4
from app.module.contact.serializer.ContactSerializerVcard4 import ContactSerializerVcard4
from app.module.contact.serializer.ContactsDeserializerVcard import ContactsDeserializerVcard
from app.module.contact.serializer.ContactsSerializerVcard import ContactsSerializerVcard


# ========== multi-card .vcf ==========

def test_contacts_round_trip():
    contacts = [CardContact(display_name="Alice", last_name="A", uid="u1"),
                CardContact(display_name="Bob", last_name="B", uid="u2")]
    text = ContactsSerializerVcard(ContactSerializerVcard4()).serialize(contacts)
    assert text.count("BEGIN:VCARD") == 2
    back = ContactsDeserializerVcard().deserialize(text)
    assert [c.display_name for c in back] == ["Alice", "Bob"]


def test_contacts_deserializer_skips_group_cards():
    doc = ("BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Alice\r\nEND:VCARD\r\n"
           "BEGIN:VCARD\r\nVERSION:4.0\r\nKIND:group\r\nFN:Team\r\nEND:VCARD\r\n")
    back = ContactsDeserializerVcard().deserialize(doc)
    assert [c.display_name for c in back] == ["Alice"]  # the group card is not a contact


# ========== distribution list (KIND:group) ==========

def _list():
    return CardList(name="Project Team", uid="list-1", description="The team",
                    member_contacts=[CardContact(uid="m1"), CardContact(uid="m2")])


def test_list_serialize_vcard4():
    text = ContactListSerializerVcard4().serialize(_list())
    assert "KIND:group" in text
    assert "FN:Project Team" in text
    assert "MEMBER:urn:uuid:m1" in text and "MEMBER:urn:uuid:m2" in text


def test_list_serialize_vcard3_uses_addressbookserver():
    text = ContactListSerializerVcard3().serialize(_list())
    assert "X-ADDRESSBOOKSERVER-KIND:group" in text
    assert "X-ADDRESSBOOKSERVER-MEMBER:urn:uuid:m1" in text
    assert "\r\nKIND:group" not in text  # no bare 4.0 KIND line (only the X-ADDRESSBOOKSERVER- one)


def test_list_round_trip_members_as_uid_refs():
    text = ContactListSerializerVcard4().serialize(_list())
    back = ContactListDeserializerVcard().deserialize(text)
    assert back.name == "Project Team"
    assert back.description == "The team"
    assert back.uid == "list-1"
    assert back.members == ["m1", "m2"]  # member UIDs, resolved to keys at import time
