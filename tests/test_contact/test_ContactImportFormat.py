"""Unit tests for the import_format provenance stamp."""
from pathlib import Path

from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.CardContactDeserializerDict import CardContactDeserializerDict
from app.module.contact.serializer.CardContactDeserializerLdif import CardContactDeserializerLdif
from app.module.contact.serializer.CardContactDeserializerVcard3 import CardContactDeserializerVcard3
from app.module.contact.serializer.CardContactDeserializerVcard4 import CardContactDeserializerVcard4
from app.module.contact.serializer.CardContactSerializerDict import CardContactSerializerDict
from app.module.contact.serializer.CardContactsDeserializerVcard import CardContactsDeserializerVcard

_FIXTURES = Path(__file__).parent / "fixtures"


def test_vcard_deserializers_stamp_format():
    card = "BEGIN:VCARD\r\nVERSION:{}\r\nFN:X\r\nEND:VCARD"
    assert CardContactDeserializerVcard4().deserialize(card.format("4.0")).import_format == ContactImportFormat.VCARD4
    assert CardContactDeserializerVcard3().deserialize(card.format("3.0")).import_format == ContactImportFormat.VCARD3


def test_ldif_stamps_format_and_captures_unknown_attrs():
    text = "dn: cn=A,ou=contacts\nobjectClass: inetOrgPerson\ncn: A\nsn: A\nx-custom: hello\n"
    contact = CardContactDeserializerLdif().deserialize(text)
    assert contact.import_format == ContactImportFormat.LDIF
    assert contact.extra_properties["x-custom"] == "hello"  # unmapped LDIF attr kept


def test_json_created_contact_is_undefined():
    contact = CardContactDeserializerDict().deserialize({"display_name": "X"})
    assert contact.import_format == ContactImportFormat.UNDEFINED


def test_dict_round_trip_preserves_import_format():
    contact = CardContact(display_name="X", import_format=ContactImportFormat.VCARD4)
    blob = CardContactSerializerDict().serialize(contact)
    assert blob["import_format"] == "vcard4"
    assert CardContactDeserializerDict().deserialize(blob).import_format == ContactImportFormat.VCARD4


def test_real_files_get_the_right_format():
    v3 = CardContactsDeserializerVcard().deserialize((_FIXTURES / "example_vcard3.vcf").read_text(encoding="utf-8"))
    v4 = CardContactsDeserializerVcard().deserialize((_FIXTURES / "example_vcard4.vcf").read_text(encoding="utf-8"))
    assert v3[0].import_format == ContactImportFormat.VCARD3
    assert v4[0].import_format == ContactImportFormat.VCARD4
