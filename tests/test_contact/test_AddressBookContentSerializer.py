"""Unit tests for the address book export serializers (contacts + lists in one document)."""
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.AddressBookContentSerializerLdif import AddressBookContentSerializerLdif
from app.module.contact.serializer.AddressBookContentSerializerVcard import AddressBookContentSerializerVcard
from app.module.contact.serializer.CardListSerializerVcard4 import CardListSerializerVcard4
from app.module.contact.serializer.CardContactSerializerVcard4 import CardContactSerializerVcard4


def _content():
    alice = CardContact(display_name="Alice", uid="u1")
    bob = CardContact(display_name="Bob", uid="u2")
    return AddressBookContent(
        contacts=[alice, bob],
        lists=[CardList(name="Team", uid="l1", member_contacts=[alice, bob])],
    )


def _vcard():
    return AddressBookContentSerializerVcard(CardContactSerializerVcard4(), CardListSerializerVcard4())


# ========== vCard ==========

def test_vcard_concatenates_contacts_then_lists():
    out = _vcard().serialize(_content())
    assert out.count("BEGIN:VCARD") == 3  # two contacts + one group card
    assert "FN:Alice" in out and "FN:Bob" in out
    assert "KIND:group" in out             # the list is exported as a group card


def test_vcard_empty_is_empty_document():
    assert _vcard().serialize(AddressBookContent([], [])) == ""


# ========== LDIF ==========

def test_ldif_single_header_with_both_record_types():
    out = AddressBookContentSerializerLdif().serialize(_content())
    assert out.count("version: 1") == 1 and out.startswith("version: 1")  # exactly one header
    assert "objectClass: inetOrgPerson" in out  # a contact record
    assert "objectClass: groupOfNames" in out   # a list record


def test_ldif_empty_is_header_only():
    assert AddressBookContentSerializerLdif().serialize(AddressBookContent([], [])) == "version: 1\n"
