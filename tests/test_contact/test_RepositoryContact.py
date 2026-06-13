"""Unit tests for RepositoryContact pure helpers (search vector + row mapping)."""
from app.config.db import tables as tbl
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.repository.RepositoryContact import RepositoryContact
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict

_COLS = tuple(col.name for col in tbl.ALL_CT_COL)
_serializer = ContactSerializerDict()


def _row(blob, **overrides):
    base = {name: None for name in _COLS}
    base.update(id=1, key="ct-k", addressbook_key="ab-k", uid="u1", kind="individual",
                last_name="Doe", first_name="John", organization=None, display_name="John Doe",
                is_deleted=False, search_vector="", contact_data=blob)
    base.update(overrides)
    return tuple(base[name] for name in _COLS)


# ========== _build_search_vector ==========

def test_build_search_vector_includes_names_org_and_emails():
    contact = CardContact(display_name="Joel Foo", organization="Acme", nickname="Jojo",
                          emails=[CardEmail(value="joel@acme.com")])
    vector = RepositoryContact._build_search_vector(contact)
    for token in ("joel", "foo", "acme", "jojo", "joel@acme.com"):
        assert token in vector


def test_build_search_vector_strips_accents():
    vector = RepositoryContact._build_search_vector(CardContact(display_name="Joël"))
    assert "joel" in vector


# ========== _row_to_contact ==========

def test_row_to_contact_rebuilds_from_blob_and_overrides_relational():
    blob = _serializer.serialize(CardContact(
        uid="u1", display_name="John Doe", first_name="John", last_name="Doe",
        kind=CardKind.INDIVIDUAL, emails=[CardEmail(value="john@x.com", types=["work"])],
    ))
    contact = RepositoryContact._row_to_contact(_row(blob, key="ct-k", last_name="Override"))
    # Content fields come from the blob...
    assert contact.emails == [CardEmail(value="john@x.com", types=["work"])]
    # ...relational columns are authoritative.
    assert contact.key == "ct-k"
    assert contact.db_id == 1
    assert contact.addressbook_key == "ab-k"
    assert contact.last_name == "Override"
