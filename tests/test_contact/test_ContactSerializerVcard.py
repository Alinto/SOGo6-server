"""Unit tests for the vCard 3.0 / 4.0 contact serializers and deserializers."""
from datetime import date

from app.module.contact.model.CardAddress import CardAddress
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardImpp import CardImpp
from app.module.contact.model.CardPhone import CardPhone
from app.module.contact.model.CardUrl import CardUrl
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.serializer.CardContactDeserializerVcard import CardContactDeserializerVcard
from app.module.contact.serializer.CardContactDeserializerVcard3 import CardContactDeserializerVcard3
from app.module.contact.serializer.CardContactDeserializerVcard4 import CardContactDeserializerVcard4
from app.module.contact.serializer.CardContactSerializerVcard3 import CardContactSerializerVcard3
from app.module.contact.serializer.CardContactSerializerVcard4 import CardContactSerializerVcard4


def _rich_contact():
    return CardContact(
        uid="u-123", kind=CardKind.INDIVIDUAL,
        display_name="John Q. Doe", first_name="John", last_name="Doe", middle_name="Quentin",
        nickname="Johnny", organization="Acme Corp", department="R&D", job_title="Engineer", role="Dev",
        emails=[CardEmail(value="john@acme.com", types=["work"], pref=1),
                CardEmail(value="j@home.test", types=["home"])],
        phones=[CardPhone(number="+33123456789", types=["cell", "voice"], pref=1)],
        addresses=[CardAddress(street="1 rue de Paris", locality="Paris", postal_code="75001",
                               country="France", types=["home"])],
        urls=[CardUrl(value="https://acme.com", type="work")],
        impp=[CardImpp(uri="xmpp:john@chat.test", type="work")],
        categories=["colleague", "vip"], note="Met at a, conference; nice",
        birthday=date(1985, 4, 15), anniversary=date(2010, 6, 1), geo="geo:48.85,2.35",
        public_key="https://acme.com/key.asc", timezone="Europe/Paris",
        extra_properties={"X-TWITTER": "@johndoe"})


def _assert_round_trip(original, text, deserializer):
    back = deserializer.deserialize(text)
    assert back.display_name == original.display_name
    assert (back.last_name, back.first_name, back.middle_name) == ("Doe", "John", "Quentin")
    assert back.nickname == "Johnny"
    assert (back.organization, back.department) == ("Acme Corp", "R&D")
    assert (back.job_title, back.role) == ("Engineer", "Dev")
    assert back.emails == original.emails
    assert back.phones == original.phones
    assert back.addresses == original.addresses
    assert back.urls == original.urls
    assert back.impp == original.impp
    assert back.categories == ["colleague", "vip"]
    assert back.note == "Met at a, conference; nice"  # comma/semicolon survive escaping
    assert back.birthday == date(1985, 4, 15)
    assert back.anniversary == date(2010, 6, 1)
    assert back.geo == "geo:48.85,2.35"
    assert back.timezone == "Europe/Paris"
    assert back.public_key == "https://acme.com/key.asc"
    assert back.uid == "u-123"
    assert back.extra_properties["X-TWITTER"] == "@johndoe"


# ========== round-trip ==========

def test_round_trip_vcard4():
    contact = _rich_contact()
    text = CardContactSerializerVcard4().serialize(contact)
    assert "VERSION:4.0" in text
    assert "KIND:individual" in text
    assert "EMAIL;TYPE=work;PREF=1:john@acme.com" in text
    _assert_round_trip(contact, text, CardContactDeserializerVcard4())


def test_round_trip_vcard3():
    contact = _rich_contact()
    text = CardContactSerializerVcard3().serialize(contact)
    assert "VERSION:3.0" in text
    assert "KIND:" not in text                      # 3.0 has no KIND for individuals
    assert "X-ANNIVERSARY:" in text                 # 3.0 anniversary is an X- property
    assert "GEO:48.85;2.35" in text                 # 3.0 geo is "lat;lon"
    assert "TYPE=work,PREF" in text                 # 3.0 marks preference with a TYPE value
    _assert_round_trip(contact, text, CardContactDeserializerVcard3())


# ========== version detection ==========

def test_detect_version_reads_declared():
    assert CardContactDeserializerVcard.detect_version("BEGIN:VCARD\r\nVERSION:3.0\r\nEND:VCARD") == "3.0"
    assert CardContactDeserializerVcard.detect_version("BEGIN:VCARD\r\nVERSION:4.0\r\nEND:VCARD") == "4.0"


def test_detect_version_defaults_when_absent():
    assert CardContactDeserializerVcard.detect_version("BEGIN:VCARD\r\nFN:X\r\nEND:VCARD") == "4.0"


# ========== leniency ==========

def test_unknown_properties_go_to_extra_without_raising():
    text = "BEGIN:VCARD\r\nVERSION:4.0\r\nFN:X\r\nX-CUSTOM:hello\r\nEND:VCARD"
    contact = CardContactDeserializerVcard4().deserialize(text)
    assert contact.display_name == "X"
    assert contact.extra_properties["X-CUSTOM"] == "hello"


def test_partial_birthday_is_preserved():
    # A year-less vCard date (--0415) can't be a date.date: kept in birthday_yearless, not dropped.
    contact = CardContactDeserializerVcard4().deserialize("BEGIN:VCARD\r\nVERSION:4.0\r\nBDAY:--0415\r\nEND:VCARD")
    assert contact.birthday is None and contact.birthday_yearless == "--04-15"
    assert "BDAY:--0415" in CardContactSerializerVcard4().serialize(contact)        # 4.0 basic
    assert "BDAY:--04-15" in CardContactSerializerVcard3().serialize(contact)       # 3.0 extended


def test_text_birthday_is_dropped_not_raised():
    contact = CardContactDeserializerVcard4().deserialize("BEGIN:VCARD\r\nVERSION:4.0\r\nBDAY:circa 1800\r\nEND:VCARD")
    assert contact.birthday is None


# ========== version-specific value forms (RFC) ==========

def test_vcard4_emits_basic_date_and_urn_uid():
    contact = CardContact(uid="abc-123", display_name="X", birthday=date(1985, 4, 15))
    text = CardContactSerializerVcard4().serialize(contact)
    assert "BDAY:19850415" in text              # 4.0 basic date form (RFC 6350 4.3.1)
    assert "UID:urn:uuid:abc-123" in text       # 4.0 UID as a URI, matching MEMBER:urn:uuid:


def test_vcard3_keeps_extended_date_and_bare_uid():
    contact = CardContact(uid="abc-123", display_name="X", birthday=date(1985, 4, 15))
    text = CardContactSerializerVcard3().serialize(contact)
    assert "BDAY:1985-04-15" in text            # 3.0 ISO extended date form
    assert "UID:abc-123" in text


def test_reader_accepts_foreign_type_pref_encoding():
    # A 4.0 file using the 3.0 "TYPE=pref" token, and a 3.0 file using a 4.0 "PREF=" parameter.
    v4 = CardContactDeserializerVcard4().deserialize(
        "BEGIN:VCARD\r\nVERSION:4.0\r\nEMAIL;TYPE=work,pref:a@x.com\r\nEND:VCARD")
    assert v4.emails[0].types == ["work"] and v4.emails[0].pref == 1
    v3 = CardContactDeserializerVcard3().deserialize(
        "BEGIN:VCARD\r\nVERSION:3.0\r\nEMAIL;TYPE=work;PREF=1:a@x.com\r\nEND:VCARD")
    assert v3.emails[0].types == ["work"] and v3.emails[0].pref == 1
