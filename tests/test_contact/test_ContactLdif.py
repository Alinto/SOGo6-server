"""Unit tests for the LDIF engine and the LDIF contact / list serializers."""
import base64

from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif
from app.module.contact.model.CardAddress import CardAddress
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardList import CardList
from app.module.contact.model.CardPhone import CardPhone
from app.module.contact.serializer.CardContactDeserializerLdif import CardContactDeserializerLdif
from app.module.contact.serializer.CardListDeserializerLdif import CardListDeserializerLdif
from app.module.contact.serializer.CardListSerializerLdif import CardListSerializerLdif
from app.module.contact.serializer.CardContactSerializerLdif import CardContactSerializerLdif
from app.module.contact.serializer.CardContactsDeserializerLdif import CardContactsDeserializerLdif


# ========== FormatEngineLdif ==========

def test_emit_attr_plain():
    assert FormatEngineLdif.emit_attr("cn", "John Doe") == "cn: John Doe"


def test_emit_attr_base64_for_non_ascii():
    line = FormatEngineLdif.emit_attr("cn", "Joël")
    assert line.startswith("cn:: ")
    assert base64.b64decode(line[len("cn:: "):]).decode("utf-8") == "Joël"


def test_parse_records_decodes_and_splits():
    text = ("dn: cn=A,ou=contacts\ncn: A\nmail: a@x.com\n\n"
            "dn: cn=B,ou=contacts\ncn:: " + base64.b64encode("Bé".encode()).decode() + "\n")
    records = FormatEngineLdif.parse_records(text)
    assert len(records) == 2
    assert ("cn", "A") in records[0] and ("mail", "a@x.com") in records[0]
    assert ("cn", "Bé") in records[1]


# ========== contact round-trip ==========

def test_contact_round_trip_maps_inetorgperson():
    contact = CardContact(
        display_name="John Doe", first_name="John", last_name="Doe", organization="Acme",
        department="R&D", job_title="Engineer", note="A note", uid="u-1",
        emails=[CardEmail(value="john@acme.com")],
        phones=[CardPhone(number="+331", types=["cell"]), CardPhone(number="+332")],
        addresses=[CardAddress(street="1 rue", locality="Paris", postal_code="75001", country="France")])
    back = CardContactDeserializerLdif().deserialize(CardContactSerializerLdif().serialize(contact))
    assert (back.display_name, back.first_name, back.last_name) == ("John Doe", "John", "Doe")
    assert (back.organization, back.department, back.job_title) == ("Acme", "R&D", "Engineer")
    assert back.note == "A note" and back.uid == "u-1"
    assert [e.value for e in back.emails] == ["john@acme.com"]
    assert sorted(p.number for p in back.phones) == ["+331", "+332"]
    assert any("cell" in p.types for p in back.phones)  # the cell phone maps to/from "mobile"
    assert back.addresses[0].locality == "Paris" and back.addresses[0].country == "France"


# ========== list (groupOfNames) ==========

def test_list_serialize_groupofnames_and_skip_in_contacts():
    card_list = CardList(name="Team", description="The team",
                         member_contacts=[CardContact(display_name="Alice", uid="m1")])
    text = CardListSerializerLdif().serialize(card_list)
    assert "objectClass: groupOfNames" in text
    assert "member: cn=Alice,ou=contacts" in text
    # A groupOfNames record must not be read back as a contact.
    assert CardContactsDeserializerLdif().deserialize(text) == []
    back = CardListDeserializerLdif().deserialize(text)
    assert back.name == "Team" and back.description == "The team"
    assert back.members == ["cn=Alice,ou=contacts"]  # member DNs, resolved at import time


def test_dn_escapes_special_characters_in_cn():
    text = CardListSerializerLdif().serialize(CardList(name="Sales, Inc. + Co"))
    assert "dn: cn=Sales\\, Inc. \\+ Co,ou=contacts" in text
