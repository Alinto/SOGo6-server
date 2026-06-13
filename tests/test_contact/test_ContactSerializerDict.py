"""Unit tests for ContactSerializerDict."""
from datetime import date

from app.module.contact.model.CardAddress import CardAddress
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardPhone import CardPhone
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict

_serializer = ContactSerializerDict()


def test_serialize_scalar_fields():
    contact = CardContact(key="k1", uid="u1", display_name="John Doe", first_name="John",
                          last_name="Doe", organization="Tech Corp", job_title="Engineer", kind=CardKind.INDIVIDUAL)
    result = _serializer.serialize(contact)
    assert result["key"] == "k1"
    assert result["display_name"] == "John Doe"
    assert result["job_title"] == "Engineer"
    assert result["kind"] == "individual"


def test_serialize_typed_subobjects():
    contact = CardContact(
        display_name="John",
        emails=[CardEmail(value="john@x.com", types=["work"], pref=1)],
        phones=[CardPhone(number="+33123", types=["cell"])],
        addresses=[CardAddress(street="1 Main St", locality="Paris", country="FR", types=["home"])],
    )
    result = _serializer.serialize(contact)
    assert result["emails"] == [{"value": "john@x.com", "types": ["work"], "pref": 1}]
    assert result["phones"][0]["number"] == "+33123"
    assert result["addresses"][0]["locality"] == "Paris"


def test_serialize_dates_as_iso():
    contact = CardContact(display_name="John", birthday=date(1990, 4, 15), anniversary=date(2020, 1, 1))
    result = _serializer.serialize(contact)
    assert result["birthday"] == "1990-04-15"
    assert result["anniversary"] == "2020-01-01"


def test_serialize_none_dates():
    result = _serializer.serialize(CardContact(display_name="John"))
    assert result["birthday"] is None
    assert result["anniversary"] is None
