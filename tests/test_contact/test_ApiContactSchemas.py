"""Unit tests for the contact API Marshmallow schemas."""
import pytest
from marshmallow import ValidationError

from app.api.v1.contact.schemas.addressbook import (
    ContactSharePatchSchema, ContactShareUserSchema, SharedAddressBookSubscribeSchema,
)
from app.api.v1.contact.schemas.contact import ContactCreateSchema, ContactPatchSchema


def test_patch_schema_does_not_inject_defaults_for_absent_fields():
    # A partial PATCH must carry only what the client sent: a load_default on a multi-valued field
    # would inject an empty list/dict and the merge would wipe the stored emails/phones/etc.
    loaded = ContactPatchSchema().load({"note": "Met at conference"})
    assert loaded == {"note": "Met at conference"}
    for field in ("emails", "phones", "addresses", "urls", "impp", "photos", "categories",
                  "extra_properties", "kind"):
        assert field not in loaded


def test_create_schema_still_defaults_absent_multivalued_fields():
    loaded = ContactCreateSchema().load({"display_name": "Alice"})
    assert loaded["emails"] == []
    assert loaded["kind"] == "individual"


# ========== shared address book subscription ==========

_SHARE_ITEM = {"c_email": "jdoe@example.org", "uid": "jdoe", "user_class": "user",
               "rights": {"can_view": True, "can_create_objects": False,
                          "can_edit_objects": False, "can_erase_objects": False}}


def test_share_subscribe_defaults_to_false():
    assert ContactSharePatchSchema().load(_SHARE_ITEM)["subscribe"] is False


def test_share_subscribe_is_never_dumped():
    assert "subscribe" not in ContactShareUserSchema().dump({**_SHARE_ITEM, "subscribe": True})


@pytest.mark.parametrize("value, expected", [(1, True), (0, False), (True, True), (False, False)])
def test_subscribe_accepts_int_and_bool(value, expected):
    assert SharedAddressBookSubscribeSchema().load({"subscribe": value})["subscribe"] is expected


def test_subscribe_is_required():
    with pytest.raises(ValidationError):
        SharedAddressBookSubscribeSchema().load({})
