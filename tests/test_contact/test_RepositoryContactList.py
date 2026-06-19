"""Unit tests for RepositoryContactList (row mapping + membership join handling)."""
from unittest.mock import MagicMock

from app.config.db import tables as tbl
from app.module.contact.repository.RepositoryContactList import RepositoryContactList

_COLS = tuple(col.name for col in tbl.ALL_LST_COL)


def _row(**overrides):
    base = {name: None for name in _COLS}
    base.update(id=1, key="lst-k", addressbook_key="ab-k", uid="u1", name="Team",
                description="The team", is_deleted=False)
    base.update(overrides)
    return tuple(base[name] for name in _COLS)


# ========== _row_to_list ==========

def test_row_to_list_maps_columns():
    card_list = RepositoryContactList._row_to_list(_row(name="Override"))
    assert card_list.key == "lst-k"
    assert card_list.id == 1
    assert card_list.addressbook_key == "ab-k"
    assert card_list.name == "Override"
    assert card_list.members == []  # never populated by the row mapper


# ========== replace_members ==========

def test_replace_members_dedups_and_inserts():
    db = MagicMock()
    RepositoryContactList(db).replace_members("lst-k", ["ct-1", "ct-2", "ct-1"])
    db.delete_row_in_table.assert_called_once()  # clears the previous membership first
    values = db.insert_in_table.call_args.kwargs["values_tuple"]
    assert values == [["lst-k", "ct-1"], ["lst-k", "ct-2"]]


def test_replace_members_empty_only_clears():
    db = MagicMock()
    RepositoryContactList(db).replace_members("lst-k", [])
    db.delete_row_in_table.assert_called_once()
    db.insert_in_table.assert_not_called()


# ========== delete ==========

def test_delete_by_key_soft_marks_is_deleted():
    db = MagicMock()
    RepositoryContactList(db).delete_by_key("ab-k", "lst-k", hard_delete=False)
    db.delete_row_in_table.assert_not_called()
    kwargs = db.update_in_table.call_args.kwargs
    cols, vals = kwargs["column_tuple"], kwargs["values_list"]
    assert vals[cols.index(tbl.COL_LST_IS_DELETED.name)] is True


def test_remove_contact_from_lists_deletes_by_contact_key():
    db = MagicMock()
    RepositoryContactList(db).remove_contact_from_lists("ct-9")
    cond = db.delete_row_in_table.call_args.kwargs["condition"]
    assert cond.param_name == tbl.COL_LM_CONTACT_KEY.name
    assert cond.param_value == "ct-9"


def test_delete_all_soft_detaches_from_book():
    db = MagicMock()
    RepositoryContactList(db).delete_all("ab-k", hard_delete=False)
    kwargs = db.update_in_table.call_args.kwargs
    cols, vals = kwargs["column_tuple"], kwargs["values_list"]
    assert vals[cols.index(tbl.COL_LST_IS_DELETED.name)] is True
    assert vals[cols.index(tbl.COL_LST_ADDRESSBOOK_KEY.name)] is None


# ========== purge_orphan_members ==========

def test_purge_orphan_members_drops_vanished_refs_only():
    db = MagicMock()
    db.select_from_table.return_value = [
        ("lst-live", "ct-live"),    # both ends present -> kept
        ("lst-gone", "ct-live"),    # list vanished -> dropped by list_key
        ("lst-live", "ct-gone"),    # contact vanished -> dropped by contact_key
    ]
    db.delete_row_in_table.return_value = 1
    RepositoryContactList(db).purge_orphan_members({"lst-live"}, {"ct-live"})
    deleted_values = {call.kwargs["condition"].param_value for call in db.delete_row_in_table.call_args_list}
    assert deleted_values == {"lst-gone", "ct-gone"}
