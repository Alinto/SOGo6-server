"""Unit tests for the JobLargeStore backends and the JobLargeRef reference."""
from unittest.mock import MagicMock

import pytest

from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef
from app.agent.jobs.job_large_store.JobLargeStoreFile import JobLargeStoreFile
from app.agent.jobs.job_large_store.JobLargeStoreInMemory import JobLargeStoreInMemory

_FILE_MODULE = "app.agent.jobs.job_large_store.JobLargeStoreFile"


# ========== JobLargeRef ==========

def test_ref_round_trips_through_dict():
    ref = JobLargeRef(content_type="text/calendar", locator="joblarge:abc")
    assert JobLargeRef.from_dict(ref.to_dict()) == ref


def test_ref_to_dict_shape():
    assert JobLargeRef("text/calendar", "/tmp/x").to_dict() == {
        "content_type": "text/calendar", "locator": "/tmp/x",
    }


# ========== InMemory backend (cache injected) ==========

def test_inmemory_round_trip():
    cache = MagicMock()
    box = {}
    cache.set.side_effect = lambda k, v, **kw: box.__setitem__(k, v)
    cache.get.side_effect = lambda k, _t: box.get(k)
    store = JobLargeStoreInMemory(cache)
    ref = store.save(b"BEGIN:VCALENDAR", "text/calendar")
    assert ref.content_type == "text/calendar"
    assert store.load(ref) == b"BEGIN:VCALENDAR"


def test_inmemory_load_missing_key_raises_not_found():
    cache = MagicMock()
    cache.get.return_value = None
    with pytest.raises(FileNotFoundError):
        JobLargeStoreInMemory(cache).load(JobLargeRef("text/calendar", "joblarge:gone"))


def test_inmemory_delete_drops_the_key():
    cache = MagicMock()
    JobLargeStoreInMemory(cache).delete(JobLargeRef("x", "joblarge:k"))
    cache.delete.assert_called_once_with("joblarge:k")


# ========== File backend ==========

def test_file_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    store = JobLargeStoreFile()
    ref = store.save(b"hello", "application/octet-stream")
    assert ref.locator.startswith(str(tmp_path))
    assert store.load(ref) == b"hello"
    assert ref.content_type == "application/octet-stream"


def test_file_delete_removes_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    store = JobLargeStoreFile()
    ref = store.save(b"bye", "text/plain")
    store.delete(ref)
    with pytest.raises(FileNotFoundError):
        store.load(ref)


def test_file_delete_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    JobLargeStoreFile().delete(JobLargeRef("x", str(tmp_path / "gone")))


def test_file_delete_refuses_path_outside_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    with pytest.raises(ValueError):
        JobLargeStoreFile().delete(JobLargeRef("x", "/etc/passwd"))


def test_file_load_missing_file_raises_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        JobLargeStoreFile().load(JobLargeRef("x", str(tmp_path / "never-written")))


def test_file_load_refuses_path_outside_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    # A crafted locator pointing outside the tmp root must be refused, even if readable.
    with pytest.raises(ValueError):
        JobLargeStoreFile().load(JobLargeRef("text/plain", "/etc/passwd"))


def test_file_load_refuses_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    with pytest.raises(ValueError):
        JobLargeStoreFile().load(JobLargeRef("x", str(tmp_path / ".." / "secret")))
