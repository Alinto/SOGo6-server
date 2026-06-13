"""Unit tests for ContactDeserializerDict."""
from datetime import date

from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.serializer.ContactDeserializerDict import ContactDeserializerDict
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict

_deserializer = ContactDeserializerDict()
_serializer = ContactSerializerDict()


def test_deserialize_minimal():
    contact = _deserializer.deserialize({"display_name": "Alice"})
    assert contact.display_name == "Alice"
    assert contact.version == "4.0"
    assert contact.kind == CardKind.INDIVIDUAL
    assert contact.emails == []


def test_deserialize_unknown_kind_falls_back_to_individual():
    contact = _deserializer.deserialize({"display_name": "X", "kind": "bogus"})
    assert contact.kind == CardKind.INDIVIDUAL


def test_deserialize_parses_date():
    contact = _deserializer.deserialize({"display_name": "X", "birthday": "1990-04-15"})
    assert contact.birthday == date(1990, 4, 15)


def test_deserialize_parses_typed_email():
    contact = _deserializer.deserialize({"display_name": "X", "emails": [{"value": "a@b.com", "types": ["work"], "pref": 1}]})
    assert contact.emails == [CardEmail(value="a@b.com", types=["work"], pref=1)]


def test_blob_round_trip_preserves_content():
    original = CardContact(
        uid="u1", display_name="John Doe", first_name="John", last_name="Doe",
        organization="Tech Corp", job_title="Engineer", kind=CardKind.ORG,
        emails=[CardEmail(value="john@x.com", types=["work"])],
        categories=["friend"], birthday=date(1990, 4, 15), note="hello",
    )
    restored = _deserializer.deserialize(_serializer.serialize(original))
    assert restored.display_name == original.display_name
    assert restored.organization == original.organization
    assert restored.job_title == original.job_title
    assert restored.kind == original.kind
    assert restored.emails == original.emails
    assert restored.categories == original.categories
    assert restored.birthday == original.birthday
    assert restored.note == original.note
