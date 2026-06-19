"""Unit tests for FileAdapterDatabase (managed media references over DbFileStorage).

The adapter builds its DbFileStorage internally, so the tests patch it with a mock and assert
delegation. They also cover the two connection modes: a provided (shared) db is reused and never
closed; without one, each operation opens and closes its own connection.
"""
from unittest.mock import MagicMock, patch

from app.utils.file.FileAdapter import FileAdapter
from app.utils.file.FileAdapterDatabase import FileAdapterDatabase
from app.utils.file.FileAdapterSource import FileAdapterSource

_MOD = "app.utils.file.FileAdapterDatabase"
_PREFIX = FileAdapter.REFERENCE_PREFIX


def _shared(storage, source=FileAdapterSource.CONTACT):
    """Adapter reusing a provided (shared) connection; its internal DbFileStorage is `storage`."""
    return FileAdapterDatabase(MagicMock(), source, db=MagicMock())


def test_save_writes_and_returns_managed_reference():
    storage = MagicMock()
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        ref = _shared(storage).save(b"\xff\xd8\xff", "image/jpeg")
    assert FileAdapter.is_reference(ref)
    key, data, content_type, source = storage.write.call_args.args
    assert ref == f"{_PREFIX}{key}"
    assert data == b"\xff\xd8\xff" and content_type == "image/jpeg"
    assert source == FileAdapterSource.CONTACT


def test_load_reads_by_key():
    storage = MagicMock()
    storage.read.return_value = (b"png", "image/png")
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        result = _shared(storage).load(f"{_PREFIX}abc")
    assert result == (b"png", "image/png")
    assert storage.read.call_args.args == ("abc",)


def test_load_ignores_plain_uri():
    storage = MagicMock()
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        assert _shared(storage).load("https://example.com/p.jpg") is None
    storage.read.assert_not_called()


def test_matches_delegates_to_storage_is_equal():
    storage = MagicMock()
    storage.is_equal.return_value = True
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        assert _shared(storage).matches(f"{_PREFIX}abc", b"png") is True
    assert storage.is_equal.call_args.args == ("abc", b"png")


def test_matches_false_on_plain_uri():
    storage = MagicMock()
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        assert _shared(storage).matches("https://example.com/p.jpg", b"png") is False
    storage.is_equal.assert_not_called()


def test_delete_targets_the_key():
    storage = MagicMock()
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        _shared(storage).delete(f"{_PREFIX}abc")
    assert storage.delete.call_args.args == ("abc",)


def test_purge_older_than_delegates_with_source():
    storage = MagicMock()
    storage.purge_older_than.return_value = 4
    with patch(f"{_MOD}.DbFileStorage", return_value=storage):
        removed = _shared(storage, FileAdapterSource.AGENT).purge_older_than(3600)
    assert removed == 4
    assert storage.purge_older_than.call_args.args == (3600, FileAdapterSource.AGENT)


# ========== Connection modes ==========

def test_shared_db_is_reused_and_never_closed():
    storage = MagicMock()
    db = MagicMock()
    with patch(f"{_MOD}.DbFileStorage", return_value=storage) as build_storage, \
         patch(f"{_MOD}.import_and_instantiate_manager") as connect:
        FileAdapterDatabase(MagicMock(), FileAdapterSource.CONTACT, db=db).delete(f"{_PREFIX}abc")
    connect.assert_not_called()        # no new connection opened
    db.close.assert_not_called()       # the owner closes it, not the adapter
    assert build_storage.call_args.args == (db,)


def test_without_db_each_operation_opens_and_closes_its_own_connection():
    storage = MagicMock()
    storage.read.return_value = (b"png", "image/png")
    opened = MagicMock()
    with patch(f"{_MOD}.DbFileStorage", return_value=storage), \
         patch(f"{_MOD}.import_and_instantiate_manager", return_value=opened) as connect:
        adapter = FileAdapterDatabase(MagicMock(), FileAdapterSource.AGENT)  # db=None
        result = adapter.load(f"{_PREFIX}abc")
    assert result == (b"png", "image/png")
    connect.assert_called_once()
    opened.connect.assert_called_once()
    opened.close.assert_called_once()
