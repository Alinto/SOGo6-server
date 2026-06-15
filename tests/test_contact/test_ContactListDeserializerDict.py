"""Unit tests for ContactListDeserializerDict."""
import pytest

from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.ContactListDeserializerDict import ContactListDeserializerDict

_deserializer = ContactListDeserializerDict()


def test_deserialize_minimal():
    card_list = _deserializer.deserialize({"name": "Team"})
    assert card_list.name == "Team"
    assert card_list.members == []
    assert card_list.key is None


def test_deserialize_with_members():
    card_list = _deserializer.deserialize({"name": "Team", "members": ["ct-1", "ct-2"]})
    assert card_list.members == ["ct-1", "ct-2"]


def test_deserialize_missing_name_raises():
    with pytest.raises(KeyError):
        _deserializer.deserialize({"description": "no name"})


def test_deserialize_with_update_applies_mutable_only():
    origin = CardList(key="lst-k", uid="u1", addressbook_key="ab-k", name="Old", members=["ct-1"])
    merged = _deserializer.deserialize_with_update(origin, {
        "name": "New", "members": ["ct-9"], "key": "hacked", "uid": "hacked", "addressbook_key": "other",
    })
    assert merged.name == "New"
    assert merged.members == ["ct-9"]
    # Identity fields are ignored by the update.
    assert merged.key == "lst-k"
    assert merged.uid == "u1"
    assert merged.addressbook_key == "ab-k"


def test_deserialize_with_update_passthrough_cardlist():
    replacement = CardList(name="Direct")
    assert _deserializer.deserialize_with_update(CardList(name="Old"), replacement) is replacement
