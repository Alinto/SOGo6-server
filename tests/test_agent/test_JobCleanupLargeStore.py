"""Unit tests for the JobCleanupLargeStore beat job."""
from unittest.mock import MagicMock, patch

from app.module.admin.jobs.JobCleanupLargeStore import JobCleanupLargeStore, JobRequestCleanupLargeStore

_JOB_MODULE = "app.module.admin.jobs.JobCleanupLargeStore"


def test_request_metadata():
    assert JobCleanupLargeStore.request_class is JobRequestCleanupLargeStore
    assert JobRequestCleanupLargeStore.name == "admin.cleanup.large_store"
    assert JobRequestCleanupLargeStore().payload() == {}


def test_process_purges_with_the_configured_age_and_returns_count():
    store = MagicMock()
    store.purge_older_than.return_value = 7
    agent = MagicMock()
    agent.get_large_store.return_value = store
    with patch(f"{_JOB_MODULE}.agent", agent), \
         patch(f"{_JOB_MODULE}.process_config.SOGO_P_AGENT_LARGE_STORE_MAX_AGE_SECONDS", 48 * 3600):
        result = JobCleanupLargeStore().process({}, user_uid=None, job_id="j-1")
    store.purge_older_than.assert_called_once_with(48 * 3600)
    assert result == {"removed": 7}
