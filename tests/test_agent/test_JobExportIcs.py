"""Unit tests for the JobExportIcs Agent job (calendar module)."""
from unittest.mock import MagicMock, patch

import pytest

from app.module.calendar.jobs.JobExportIcs import JobExportIcs
from app.module.calendar.jobs.JobRequestExportIcs import JobRequestExportIcs

from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef

_JOB_MODULE = "app.module.calendar.jobs.JobExportIcs"
# InterfaceAgentCalendar and the agent singleton are imported at the top of the job module.
_INTERFACE = f"{_JOB_MODULE}.InterfaceAgentCalendar"
_AGENT = f"{_JOB_MODULE}.agent"


def _save_agent(ref):
    """An agent whose get_large_store().save returns ``ref``; returns (agent, store)."""
    store = MagicMock()
    store.save.return_value = ref
    agent = MagicMock()
    agent.get_large_store.return_value = store
    return agent, store


def _payload(calendar_key="cal-1", date_start=None, date_end=None):
    return JobRequestExportIcs(
        calendar_key=calendar_key, date_start=date_start, date_end=date_end,
    ).payload()


def test_request_metadata_is_single_source_of_truth():
    assert JobExportIcs.request_class is JobRequestExportIcs
    assert JobRequestExportIcs.name == "calendar.export.ics"
    assert JobRequestExportIcs.resume is False
    assert JobRequestExportIcs.max_concurrent == 1


def test_process_rejects_missing_user_uid():
    job = JobExportIcs()
    with pytest.raises(ValueError):
        job.process(_payload(), user_uid=None, job_id="j-1")


def test_public_payload_is_identity_by_default():
    # JobExportIcs does not override public_payload - the export payload carries
    # no secret, so the owner sees it unchanged.
    job = JobExportIcs()
    payload = _payload(calendar_key="cal-1")
    assert job.public_payload(payload) == payload


def test_process_serialises_and_offloads_result():
    job = JobExportIcs()
    inter = MagicMock()
    inter.export_calendar.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    ref = JobLargeRef(content_type="text/calendar", locator="joblarge:abc")
    agent, store = _save_agent(ref)
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, agent):
        result = job.process(_payload(calendar_key="cal-9"), user_uid="alice", job_id="j-1")

    assert result["large_result"] == ref.to_dict()
    assert result["filename"] == "cal-9.ics"
    assert result["size_bytes"] == len("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n".encode("utf-8"))
    # The ICS bytes are what gets offloaded, tagged as a calendar.
    store.save.assert_called_once()
    saved_bytes, saved_type = store.save.call_args.args
    assert saved_bytes.startswith(b"BEGIN:VCALENDAR")
    assert saved_type == "text/calendar"


def test_process_forwards_date_bounds_to_interface():
    job = JobExportIcs()
    inter = MagicMock()
    inter.export_calendar.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    agent, _ = _save_agent(JobLargeRef("text/calendar", "k"))
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, agent):
        job.process(
            _payload(date_start="2026-01-01T00:00:00Z", date_end="2026-12-31T23:59:59Z"),
            user_uid="alice", job_id="j-1",
        )
    kwargs = inter.export_calendar.call_args.kwargs
    assert kwargs["date_start"] is not None
    assert kwargs["date_end"] is not None
