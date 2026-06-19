"""Unit tests for the contact API Marshmallow schemas."""
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
