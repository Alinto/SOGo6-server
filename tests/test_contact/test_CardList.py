"""Unit tests for the CardList model (mutable-field gating)."""
from app.module.contact.model.CardList import CardList


def _list(**kwargs):
    defaults = {"name": "Team", "key": "l1", "addressbook_key": "ab-k", "uid": "u1"}
    defaults.update(kwargs)
    return CardList(**defaults)


def test_apply_update_applies_mutable_fields():
    lst = _list(name="Old", description="d", members=["c1"])
    lst.apply_update({"name": "New", "description": "d2", "members": ["c1", "c2"]})
    assert lst.name == "New"
    assert lst.description == "d2"
    assert lst.members == ["c1", "c2"]


def test_apply_update_ignores_immutable_and_unknown_fields():
    lst = _list(key="l1", addressbook_key="ab-k", uid="u1")
    lst.apply_update({"key": "hacked", "addressbook_key": "other", "uid": "x", "unknown": 1})
    assert lst.key == "l1"
    assert lst.addressbook_key == "ab-k"
    assert lst.uid == "u1"
