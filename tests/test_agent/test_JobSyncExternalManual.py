"""Unit tests for the JobSyncExternalManual Agent job (calendar module)."""
from unittest.mock import MagicMock, patch

import pytest

from app.module.calendar.jobs.JobSyncExternalManual import JobSyncExternalManual
from app.module.calendar.jobs.JobRequestSyncExternalManual import JobRequestSyncExternalManual
from app.module.calendar.model.CalSyncResult import CalSyncResult

_JOB_MODULE = "app.module.calendar.jobs.JobSyncExternalManual"
_INTERFACE = f"{_JOB_MODULE}.InterfaceAgentCalendar"


def test_request_metadata():
    assert JobSyncExternalManual.request_class is JobRequestSyncExternalManual
    assert JobRequestSyncExternalManual.name == "calendar.sync.external.manual"
    assert JobRequestSyncExternalManual.max_concurrent == 0
    assert JobRequestSyncExternalManual(calendar_key="c1").payload() == {"calendar_key": "c1"}


def test_process_rejects_missing_user_uid():
    with pytest.raises(ValueError):
        JobSyncExternalManual().process({"calendar_key": "c1"}, user_uid=None, job_id="j-1")


def test_process_syncs_and_returns_counters():
    inter = MagicMock()
    inter.sync_external_calendar.return_value = CalSyncResult(inserted=2, updated=1, deleted=0, total=3, skipped=0)
    with patch(_INTERFACE, return_value=inter):
        result = JobSyncExternalManual().process({"calendar_key": "c1"}, user_uid="alice", job_id="j-1")
    inter.sync_external_calendar.assert_called_once_with("c1")
    assert result == {"inserted": 2, "updated": 1, "deleted": 0, "total": 3, "skipped": 0}
