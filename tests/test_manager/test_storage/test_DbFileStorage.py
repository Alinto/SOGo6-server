"""Unit tests for DbFileStorage (binary blob store over sogo6_file_storage)."""
import hashlib
from unittest.mock import MagicMock

from app.config.db import tables as tbl
from app.manager.storage.DbFileStorage import DbFileStorage


def test_write_inserts_key_source_data_content_type_and_hash():
    db = MagicMock()
    DbFileStorage(db).write("k1", b"\xff\xd8\xff", "image/jpeg", "contact")
    kwargs = db.insert_in_table.call_args.kwargs
    cols, values = kwargs["column_tuple"], kwargs["values_tuple"][0]
    assert values[cols.index(tbl.COL_FS_KEY.name)] == "k1"
    assert values[cols.index(tbl.COL_FS_SOURCE.name)] == "contact"
    assert values[cols.index(tbl.COL_FS_DATA.name)] == b"\xff\xd8\xff"
    assert values[cols.index(tbl.COL_FS_CONTENT_TYPE.name)] == "image/jpeg"
    assert values[cols.index(tbl.COL_FS_CONTENT_HASH.name)] == hashlib.sha256(b"\xff\xd8\xff").hexdigest()


def test_is_equal_true_on_matching_content():
    db = MagicMock()
    db.select_from_table.return_value = iter([(hashlib.sha256(b"png").hexdigest(),)])
    assert DbFileStorage(db).is_equal("k1", b"png", "contact") is True


def test_is_equal_false_on_different_content():
    db = MagicMock()
    db.select_from_table.return_value = iter([(hashlib.sha256(b"png").hexdigest(),)])
    assert DbFileStorage(db).is_equal("k1", b"other", "contact") is False


def test_is_equal_false_when_absent():
    db = MagicMock()
    db.select_from_table.return_value = iter([])
    assert DbFileStorage(db).is_equal("missing", b"png", "contact") is False


def test_read_returns_bytes_and_content_type():
    db = MagicMock()
    db.select_from_table.return_value = iter([(memoryview(b"png-bytes"), "image/png")])
    data, content_type = DbFileStorage(db).read("k1", "contact")
    assert data == b"png-bytes" and isinstance(data, bytes)  # memoryview coerced to bytes
    assert content_type == "image/png"


def test_read_returns_none_when_absent():
    db = MagicMock()
    db.select_from_table.return_value = iter([])
    assert DbFileStorage(db).read("missing", "contact") is None


def test_read_is_scoped_by_key_and_source():
    db = MagicMock()
    db.select_from_table.return_value = iter([(memoryview(b"x"), "image/png")])
    DbFileStorage(db).read("k1", "agent")
    cond = db.select_from_table.call_args.kwargs["condition"]
    assert cond.conditions[0].param_name == tbl.COL_FS_KEY.name and cond.conditions[0].param_value == "k1"
    assert cond.conditions[1].param_name == tbl.COL_FS_SOURCE.name and cond.conditions[1].param_value == "agent"


def test_delete_targets_the_key_within_its_source():
    db = MagicMock()
    DbFileStorage(db).delete("k1", "contact")
    cond = db.delete_row_in_table.call_args.kwargs["condition"]
    assert cond.conditions[0].param_name == tbl.COL_FS_KEY.name and cond.conditions[0].param_value == "k1"
    assert cond.conditions[1].param_name == tbl.COL_FS_SOURCE.name and cond.conditions[1].param_value == "contact"


def test_all_keys_returns_every_stored_key_of_the_source():
    db = MagicMock()
    db.select_from_table.return_value = iter([("k1",), ("k2",)])
    assert DbFileStorage(db).all_keys("contact") == {"k1", "k2"}
    assert db.select_from_table.call_args.kwargs["condition"].param_value == "contact"


def test_purge_older_than_deletes_by_source_and_age():
    db = MagicMock()
    db.delete_row_in_table.return_value = 3
    assert DbFileStorage(db).purge_older_than(3600, "agent") == 3
    cond = db.delete_row_in_table.call_args.kwargs["condition"]
    assert cond.conditions[0].param_name == tbl.COL_FS_SOURCE.name and cond.conditions[0].param_value == "agent"
    assert cond.conditions[1].param_name == tbl.COL_FS_CREATED_AT.name
