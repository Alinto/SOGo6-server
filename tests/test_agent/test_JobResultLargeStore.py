"""Unit tests for the JobResultLargeStore backends and the get() selector."""
from unittest.mock import MagicMock, patch

import pytest

from app.agent.jobs.job_result_large_store.JobResultLargeStorage import JobResultLargeStorage
from app.agent.jobs.job_result_large_store.JobResultLargeStore import JobResultLargeStore
from app.agent.jobs.job_result_large_store.JobResultLargeStoreFile import JobResultLargeStoreFile
from app.agent.jobs.job_result_large_store.JobResultLargeStoreInMemory import JobResultLargeStoreInMemory

_INMEM_MODULE = "app.agent.jobs.job_result_large_store.JobResultLargeStoreInMemory"
_FILE_MODULE = "app.agent.jobs.job_result_large_store.JobResultLargeStoreFile"
_STORE_MODULE = "app.agent.jobs.job_result_large_store.JobResultLargeStore"


# ========== InMemory backend ==========

def test_inmemory_round_trip():
    cache = MagicMock()
    store_box: dict = {}
    cache.set.side_effect = lambda k, v, **kw: store_box.__setitem__(k, v)
    cache.get.side_effect = lambda k, _t: store_box.get(k)
    with patch(f"{_INMEM_MODULE}.sogo_cache", return_value=cache):
        store = JobResultLargeStoreInMemory()
        ref = store.save(b"BEGIN:VCALENDAR", "text/calendar")
        assert ref["storage"] == "in_memory"
        assert ref["content_type"] == "text/calendar"
        content, ctype = store.load(ref)
    assert content == b"BEGIN:VCALENDAR"
    assert ctype == "text/calendar"


def test_inmemory_load_rejects_wrong_backend():
    store = JobResultLargeStoreInMemory()
    with pytest.raises(ValueError):
        store.load({"storage": "file", "path": "/tmp/x"})


def test_inmemory_load_missing_key_raises_not_found():
    cache = MagicMock()
    cache.get.return_value = None
    with patch(f"{_INMEM_MODULE}.sogo_cache", return_value=cache):
        store = JobResultLargeStoreInMemory()
        with pytest.raises(FileNotFoundError):
            store.load({"storage": "in_memory", "key": "jobresult:gone"})


# ========== File backend ==========

def test_file_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    store = JobResultLargeStoreFile()
    ref = store.save(b"hello", "application/octet-stream")
    assert ref["storage"] == "file"
    assert ref["path"].startswith(str(tmp_path))
    content, ctype = store.load(ref)
    assert content == b"hello"
    assert ctype == "application/octet-stream"


def test_file_load_rejects_wrong_backend():
    store = JobResultLargeStoreFile()
    with pytest.raises(ValueError):
        store.load({"storage": "in_memory", "key": "x"})


def test_file_load_missing_file_raises_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    store = JobResultLargeStoreFile()
    ref = {"storage": "file", "path": str(tmp_path / "never-written"), "content_type": "x"}
    with pytest.raises(FileNotFoundError):
        store.load(ref)


def test_file_load_refuses_path_outside_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    store = JobResultLargeStoreFile()
    # A crafted ref pointing outside the tmp root must be refused, even if readable.
    ref = {"storage": "file", "path": "/etc/passwd", "content_type": "text/plain"}
    with pytest.raises(ValueError):
        store.load(ref)


def test_file_load_refuses_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    store = JobResultLargeStoreFile()
    ref = {"storage": "file", "path": str(tmp_path / ".." / "secret"), "content_type": "x"}
    with pytest.raises(ValueError):
        store.load(ref)


# ========== JobResultLargeStore.get() selector ==========

def test_get_returns_inmemory_by_default():
    with patch(f"{_STORE_MODULE}.JOB_RESULT_LARGE_STORAGE", JobResultLargeStorage.IN_MEMORY):
        assert isinstance(JobResultLargeStore.get(), JobResultLargeStoreInMemory)


def test_get_returns_file_when_configured():
    with patch(f"{_STORE_MODULE}.JOB_RESULT_LARGE_STORAGE", JobResultLargeStorage.FILE):
        assert isinstance(JobResultLargeStore.get(), JobResultLargeStoreFile)


# ========== JobResultLargeStore.load_ref() follows the ref, not the config ==========

def test_load_ref_file_roundtrip_ignores_global_config(tmp_path, monkeypatch):
    # Save in FILE, then load_ref while the global default is IN_MEMORY: the ref wins.
    monkeypatch.setattr(f"{_FILE_MODULE}.process_config.SOGO_P_TMP_PATH", str(tmp_path))
    ref = JobResultLargeStoreFile().save(b"hello", "text/plain")
    with patch(f"{_STORE_MODULE}.JOB_RESULT_LARGE_STORAGE", JobResultLargeStorage.IN_MEMORY):
        content, ctype = JobResultLargeStore.load_ref(ref)
    assert content == b"hello"
    assert ctype == "text/plain"


def test_load_ref_inmemory_dispatch():
    cache = MagicMock()
    store_box = {"jobresult:k": {"content_b64": "aGk=", "content_type": "text/plain"}}  # "hi"
    cache.get.side_effect = lambda k, _t: store_box.get(k)
    ref = {"storage": "in_memory", "key": "jobresult:k", "content_type": "text/plain"}
    with patch(f"{_INMEM_MODULE}.sogo_cache", return_value=cache):
        content, ctype = JobResultLargeStore.load_ref(ref)
    assert content == b"hi"
    assert ctype == "text/plain"


def test_load_ref_rejects_unknown_storage():
    with pytest.raises(ValueError):
        JobResultLargeStore.load_ref({"storage": "s3", "path": "/x"})
