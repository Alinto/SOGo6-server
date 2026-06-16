"""Unit tests for the import_format provenance stamp."""
from pathlib import Path

from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.ContactDeserializerDict import ContactDeserializerDict
from app.module.contact.serializer.ContactDeserializerLdif import ContactDeserializerLdif
from app.module.contact.serializer.ContactDeserializerVcard3 import ContactDeserializerVcard3
from app.module.contact.serializer.ContactDeserializerVcard4 import ContactDeserializerVcard4
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict
from app.module.contact.serializer.ContactsDeserializerVcard import ContactsDeserializerVcard

_FIXTURES = Path(__file__).parent / "fixtures"


def test_vcard_deserializers_stamp_format():
    card = "BEGIN:VCARD\r\nVERSION:{}\r\nFN:X\r\nEND:VCARD"
    assert ContactDeserializerVcard4().deserialize(card.format("4.0")).import_format == ContactImportFormat.VCARD4
    assert ContactDeserializerVcard3().deserialize(card.format("3.0")).import_format == ContactImportFormat.VCARD3


def test_ldif_stamps_format_and_captures_unknown_attrs():
    text = "dn: cn=A,ou=contacts\nobjectClass: inetOrgPerson\ncn: A\nsn: A\nx-custom: hello\n"
    contact = ContactDeserializerLdif().deserialize(text)
    assert contact.import_format == ContactImportFormat.LDIF
    assert contact.extra_properties["x-custom"] == "hello"  # unmapped LDIF attr kept


def test_json_created_contact_is_undefined():
    contact = ContactDeserializerDict().deserialize({"display_name": "X"})
    assert contact.import_format == ContactImportFormat.UNDEFINED


def test_dict_round_trip_preserves_import_format():
    contact = CardContact(display_name="X", import_format=ContactImportFormat.VCARD4)
    blob = ContactSerializerDict().serialize(contact)
    assert blob["import_format"] == "vcard4"
    assert ContactDeserializerDict().deserialize(blob).import_format == ContactImportFormat.VCARD4


def test_real_files_get_the_right_format():
    v3 = ContactsDeserializerVcard().deserialize((_FIXTURES / "example_vcard3.vcf").read_text(encoding="utf-8"))
    v4 = ContactsDeserializerVcard().deserialize((_FIXTURES / "example_vcard4.vcf").read_text(encoding="utf-8"))
    assert v3[0].import_format == ContactImportFormat.VCARD3
    assert v4[0].import_format == ContactImportFormat.VCARD4
