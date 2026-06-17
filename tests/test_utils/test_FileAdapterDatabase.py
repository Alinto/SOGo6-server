"""Unit tests for FileAdapterDatabase (managed media references over DbFileStorage)."""
from unittest.mock import MagicMock

from app.utils.file.FileAdapter import FileAdapter
from app.utils.file.FileAdapterDatabase import FileAdapterDatabase


def test_save_writes_and_returns_managed_reference():
    storage = MagicMock()
    ref = FileAdapterDatabase(storage).save(b"\xff\xd8\xff", "image/jpeg")
    assert FileAdapter.is_reference(ref)
    key, data, content_type = storage.write.call_args.args
    assert ref == f"{FileAdapter.REFERENCE_PREFIX}{key}"
    assert data == b"\xff\xd8\xff" and content_type == "image/jpeg"


def test_load_reads_by_key():
    storage = MagicMock()
    storage.read.return_value = (b"png", "image/png")
    adapter = FileAdapterDatabase(storage)
    assert adapter.load(f"{FileAdapter.REFERENCE_PREFIX}abc") == (b"png", "image/png")
    assert storage.read.call_args.args == ("abc",)


def test_load_ignores_plain_uri():
    storage = MagicMock()
    assert FileAdapterDatabase(storage).load("https://example.com/p.jpg") is None
    storage.read.assert_not_called()


def test_matches_delegates_to_storage_is_equal():
    storage = MagicMock()
    storage.is_equal.return_value = True
    assert FileAdapterDatabase(storage).matches(f"{FileAdapter.REFERENCE_PREFIX}abc", b"png") is True
    assert storage.is_equal.call_args.args == ("abc", b"png")


def test_matches_false_on_plain_uri():
    storage = MagicMock()
    assert FileAdapterDatabase(storage).matches("https://example.com/p.jpg", b"png") is False
    storage.is_equal.assert_not_called()


def test_delete_targets_the_key():
    storage = MagicMock()
    FileAdapterDatabase(storage).delete(f"{FileAdapter.REFERENCE_PREFIX}abc")
    assert storage.delete.call_args.args == ("abc",)


def test_delete_ignores_plain_uri():
    storage = MagicMock()
    FileAdapterDatabase(storage).delete("https://example.com/p.jpg")
    storage.delete.assert_not_called()
