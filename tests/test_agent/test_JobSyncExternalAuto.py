"""Unit tests for the JobSyncExternalAuto periodic Agent job (calendar module)."""
from unittest.mock import MagicMock, patch

from app.module.calendar.jobs.JobSyncExternalAuto import JobSyncExternalAuto, JobRequestSyncExternalAuto

_JOB_MODULE = "app.module.calendar.jobs.JobSyncExternalAuto"


def test_request_metadata():
    assert JobSyncExternalAuto.request_class is JobRequestSyncExternalAuto
    assert JobRequestSyncExternalAuto.name == "calendar.sync.external.auto"
    assert JobRequestSyncExternalAuto.cron == "*/5 * * * *"
    assert JobRequestSyncExternalAuto().payload() == {}


def test_process_delegates_to_the_module_sweep():
    module = MagicMock()
    module.sync_all_due_external.return_value = {"total": 3, "synced": 2, "failed": 1, "skipped": 0}
    with patch(f"{_JOB_MODULE}.ModuleCalendar", return_value=module), patch(f"{_JOB_MODULE}.sogo_cache"):
        result = JobSyncExternalAuto().process({}, user_uid=None, job_id="j-1")
    module.sync_all_due_external.assert_called_once()
    assert result == {"total": 3, "synced": 2, "failed": 1, "skipped": 0}
