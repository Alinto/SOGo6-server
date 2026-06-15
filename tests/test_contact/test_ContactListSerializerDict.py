"""Unit tests for ContactListSerializerDict."""
from datetime import datetime, timezone

from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.ContactListSerializerDict import ContactListSerializerDict

_serializer = ContactListSerializerDict()


def test_serialize_exposes_members_and_count():
    card_list = CardList(key="lst-k", uid="u1", name="Team", description="The team",
                         members=["ct-1", "ct-2"])
    out = _serializer.serialize(card_list)
    assert out["key"] == "lst-k"
    assert out["name"] == "Team"
    assert out["members"] == ["ct-1", "ct-2"]
    assert out["member_count"] == 2


def test_serialize_empty_members():
    out = _serializer.serialize(CardList(name="Empty"))
    assert out["members"] == []
    assert out["member_count"] == 0


def test_serialize_timestamps_iso_or_none():
    out = _serializer.serialize(CardList(name="T", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))
    assert out["created_at"].startswith("2026-01-02")
    assert out["updated_at"] is None
