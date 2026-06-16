"""End-to-end vCard tests against real-world .vcf files (fixtures), exercising parser leniency."""
from pathlib import Path

from app.module.contact.serializer.ContactDeserializerVcard import ContactDeserializerVcard
from app.module.contact.serializer.ContactSerializerVcard3 import ContactSerializerVcard3
from app.module.contact.serializer.ContactSerializerVcard4 import ContactSerializerVcard4
from app.module.contact.serializer.ContactsDeserializerVcard import ContactsDeserializerVcard

_FIXTURES = Path(__file__).parent / "fixtures"
_VCARD3 = (_FIXTURES / "example_vcard3.vcf").read_text(encoding="utf-8")
_VCARD4 = (_FIXTURES / "example_vcard4.vcf").read_text(encoding="utf-8")


def test_detect_version_on_real_files():
    assert ContactDeserializerVcard.detect_version(_VCARD3) == "3.0"
    assert ContactDeserializerVcard.detect_version(_VCARD4) == "4.0"


def test_parse_real_vcard3():
    contacts = ContactsDeserializerVcard().deserialize(_VCARD3)
    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.display_name == "John Doe"
    assert (contact.last_name, contact.first_name) == ("Doe", "John")
    assert "forrestgump@example.com" in [email.value for email in contact.emails]
    assert len(contact.phones) == 3
    # The embedded AGENT vCard is an unknown property kept verbatim, not a crash.
    assert "AGENT" in contact.extra_properties


def test_parse_real_vcard4():
    contacts = ContactsDeserializerVcard().deserialize(_VCARD4)
    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.display_name == "NOM DE FAMILLE Prénom"   # accents preserved
    assert contact.last_name == "NOM DE FAMILLE"
    assert "votre.adresse@mail.com" in [email.value for email in contact.emails]
    assert (contact.organization, contact.department) == ("Lieu de travail", "Service")
    assert contact.birthday is None                          # "Année-mois-jour" is not a real date
    assert "GENDER" in contact.extra_properties              # unmapped property kept
    assert len(contact.addresses) == 2                       # both ADR (work + home), quirks tolerated
    assert any(addr.country == "Pays" for addr in contact.addresses)


def test_reserialize_real_files_is_stable():
    # Parsing then re-serializing then re-parsing must converge (our own output is clean).
    for raw, serializer, deserializer_version in (
        (_VCARD3, ContactSerializerVcard3(), "3.0"),
        (_VCARD4, ContactSerializerVcard4(), "4.0"),
    ):
        first = ContactsDeserializerVcard().deserialize(raw)[0]
        text = serializer.serialize(first)
        assert ContactDeserializerVcard.detect_version(text) == deserializer_version
        second = ContactsDeserializerVcard().deserialize(text)[0]
        assert second.display_name == first.display_name
        assert [e.value for e in second.emails] == [e.value for e in first.emails]
        assert [p.number for p in second.phones] == [p.number for p in first.phones]
        assert second.organization == first.organization
        assert second.addresses == first.addresses
