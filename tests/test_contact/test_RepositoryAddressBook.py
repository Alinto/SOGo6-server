"""Unit tests for RepositoryAddressBook row mapping."""
from app.config.db import tables as tbl
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.repository.RepositoryAddressBook import RepositoryAddressBook

_COLS = tuple(col.name for col in tbl.ALL_AB_COL)


def _row(**overrides):
    base = {name: None for name in _COLS}
    base.update(id=1, key="ab-k", user_uid="alice@example.com", is_default=True,
                source_type="local", name="Personal", description="d", ctag=3, sync_config=None)
    base.update(overrides)
    return tuple(base[name] for name in _COLS)


def test_row_to_addressbook_maps_fields():
    book = RepositoryAddressBook._row_to_addressbook(_row())
    assert book.id == 1
    assert book.key == "ab-k"
    assert book.user_uid == "alice@example.com"
    assert book.is_default is True
    assert book.source_type == CardSourceType.LOCAL
    assert book.name == "Personal"
    assert book.ctag == 3


def test_row_to_addressbook_carddav_source():
    book = RepositoryAddressBook._row_to_addressbook(_row(source_type="carddav"))
    assert book.source_type == CardSourceType.CARDDAV
