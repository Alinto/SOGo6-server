"""Unit tests for the JobImportIcs Agent job (calendar module)."""
from unittest.mock import MagicMock, patch

import pytest

from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef
from app.module.calendar.jobs.JobImportIcs import JobImportIcs
from app.module.calendar.jobs.JobRequestImportIcs import JobRequestImportIcs
from app.module.calendar.model.CalSyncResult import CalSyncResult

_JOB_MODULE = "app.module.calendar.jobs.JobImportIcs"
# InterfaceAgentCalendar and sogo_agent are imported at the top of the job module.
_INTERFACE = f"{_JOB_MODULE}.InterfaceAgentCalendar"
_AGENT = f"{_JOB_MODULE}.sogo_agent"
# Serialised JobLargeRef (what to_dict() produces, what travels on the wire).
_REF = {"content_type": "text/calendar", "locator": "joblarge:abc"}
_UNSET = object()


def _payload(calendar_key="cal-1", source_ref=_UNSET):
    ref = dict(_REF) if source_ref is _UNSET else source_ref
    return {"calendar_key": calendar_key, "source_ref": ref}


def _store_agent(content=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"):
    """A sogo_agent() whose large_store.load returns bytes; returns (agent, store)."""
    store = MagicMock()
    store.load.return_value = content
    agent = MagicMock()
    agent.large_store = store
    return agent, store


def test_request_metadata():
    assert JobImportIcs.request_class is JobRequestImportIcs
    assert JobRequestImportIcs.name == "calendar.import.ics"
    assert JobRequestImportIcs.resume is False


def test_public_payload_strips_the_source_ref():
    # The blob locator (a file path / Redis key) must not leak through GET /jobs/<id>.
    public = JobImportIcs().public_payload(_payload(calendar_key="cal-1"))
    assert public == {"calendar_key": "cal-1"}
    assert "source_ref" not in public


def test_process_rejects_missing_user_uid_but_still_drops_the_blob():
    agent, store = _store_agent()
    with patch(_AGENT, return_value=agent):
        with pytest.raises(ValueError):
            JobImportIcs().process(_payload(), user_uid=None, job_id="j-1")
    # An input blob is single-use: it must be dropped even on a rejected job.
    store.delete.assert_called_once_with(JobLargeRef.from_dict(_REF))


def test_process_rejects_missing_source_ref():
    with pytest.raises(ValueError):
        JobImportIcs().process(_payload(source_ref=None), user_uid="alice", job_id="j-1")


def test_process_loads_imports_and_deletes_the_blob():
    inter = MagicMock()
    inter.import_calendar.return_value = CalSyncResult(inserted=3, updated=1, deleted=0, total=4, skipped=2)
    agent, store = _store_agent()
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, return_value=agent):
        result = JobImportIcs().process(_payload(calendar_key="cal-9"), user_uid="alice", job_id="j-1")

    assert result == {"inserted": 3, "updated": 1, "deleted": 0, "total": 4, "skipped": 2}
    store.load.assert_called_once_with(JobLargeRef.from_dict(_REF))
    inter.import_calendar.assert_called_once_with("cal-9", "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    # The input blob is consumed: it must be deleted.
    store.delete.assert_called_once_with(JobLargeRef.from_dict(_REF))


def test_process_deletes_the_blob_even_on_failure():
    inter = MagicMock()
    inter.import_calendar.side_effect = RuntimeError("boom")
    agent, store = _store_agent(b"BEGIN:VCALENDAR")
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, return_value=agent):
        with pytest.raises(RuntimeError):
            JobImportIcs().process(_payload(), user_uid="alice", job_id="j-1")
    store.delete.assert_called_once_with(JobLargeRef.from_dict(_REF))
