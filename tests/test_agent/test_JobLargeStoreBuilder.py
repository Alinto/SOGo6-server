"""JobLargeStoreBuilder picks the backend from SOGO_P_AGENT_LARGE_STORE."""
from unittest.mock import MagicMock

import pytest

from app.agent.jobs.job_large_store.JobLargeStoreBuilder import JobLargeStoreBuilder
from app.agent.jobs.job_large_store.JobLargeStoreFile import JobLargeStoreFile
from app.agent.jobs.job_large_store.JobLargeStoreInMemory import JobLargeStoreInMemory


class _Setting:
    def __init__(self, value):
        self.SOGO_P_AGENT_LARGE_STORE = value


def test_build_file():
    assert isinstance(JobLargeStoreBuilder.build(_Setting("file"), MagicMock()), JobLargeStoreFile)


def test_build_in_memory_injects_the_cache():
    cache = MagicMock()
    store = JobLargeStoreBuilder.build(_Setting("in_memory"), cache)
    assert isinstance(store, JobLargeStoreInMemory)
    assert store._cache is cache


def test_build_rejects_unknown_backend():
    with pytest.raises(ValueError):
        JobLargeStoreBuilder.build(_Setting("s3"), MagicMock())
