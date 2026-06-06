"""ClientAgent builds the large-blob backend from the injected JobLargeStorage."""
from unittest.mock import MagicMock

from app.agent.jobs.job_large_store.JobLargeStorage import JobLargeStorage
from app.agent.jobs.job_large_store.JobLargeStoreFile import JobLargeStoreFile
from app.agent.jobs.job_large_store.JobLargeStoreInMemory import JobLargeStoreInMemory
from app.manager.agent.ClientAgent import ClientAgent


def test_build_large_store_file():
    assert isinstance(ClientAgent._build_large_store(JobLargeStorage.FILE, MagicMock()), JobLargeStoreFile)


def test_build_large_store_in_memory_gets_the_cache_injected():
    cache = MagicMock()
    store = ClientAgent._build_large_store(JobLargeStorage.IN_MEMORY, cache)
    assert isinstance(store, JobLargeStoreInMemory)
    assert store._cache is cache
