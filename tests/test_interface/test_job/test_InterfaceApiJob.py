"""Unit tests for InterfaceApiJob.

Covers the get_job (state envelope) and get_result (large blob) flows, plus
each error case: 404 unknown, 403 not-owner, 409 not-ready, 410 no-result.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus
from app.interface.job.InterfaceApiJob import InterfaceApiJob
from app.utils import errors as err


_UTC = timezone.utc


def _user(uid="alice"):
    u = MagicMock()
    u.uid = uid
    return u


def _state(
    *, owner="alice", status=JobStatus.SUCCESS, result=None, job_id="job-1",
):
    return JobState(
        job_id=job_id, name="calendar.export.ics", status=status,
        user_uid=owner, date_planned=datetime(2026, 6, 1, tzinfo=_UTC),
        result=result,
    )


# ========== get_job ==========

def test_get_job_returns_state_dict_for_owner():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner="alice")
        body, status = inter.get_job("job-1")
    assert status == 200
    assert body["error_code"] == err.ERROR_NO_ERROR.c
    assert body["data"]["status"] == "success"
    assert body["data"]["user_uid"] == "alice"


def test_get_job_returns_not_found_when_state_missing():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = None
        body, _ = inter.get_job("ghost")
    assert body["error_code"] == err.ERROR_JOB_NOT_FOUND.c
    assert body["data"] is None


def test_get_job_returns_forbidden_when_not_owner():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner="bob")
        body, _ = inter.get_job("job-1")
    assert body["error_code"] == err.ERROR_JOB_FORBIDDEN.c


def test_get_job_applies_handler_public_payload_redaction():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(owner="alice")
    state.payload = {"calendar_key": "cal-1", "token": "secret"}
    handler = MagicMock()
    handler.public_payload.return_value = {"calendar_key": "cal-1"}  # token stripped
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        agent.return_value.get_job_handler.return_value = handler
        body, _ = inter.get_job("job-1")
    handler.public_payload.assert_called_once_with({"calendar_key": "cal-1", "token": "secret"})
    assert body["data"]["payload"] == {"calendar_key": "cal-1"}


def test_get_job_keeps_payload_when_handler_unknown():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(owner="alice")
    state.payload = {"calendar_key": "cal-1"}
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        agent.return_value.get_job_handler.return_value = None
        body, _ = inter.get_job("job-1")
    assert body["data"]["payload"] == {"calendar_key": "cal-1"}


# ========== get_result ==========

def test_get_result_streams_blob_with_native_content_type():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": {"key": "x"}, "filename": "cal.ics"})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent, \
         patch("app.interface.job.InterfaceApiJob.JobResultLargeStore.load_ref") as load_ref:
        agent.return_value.get.return_value = state
        load_ref.return_value = (b"BEGIN:VCALENDAR\r\n", "text/calendar")
        body, status, headers = inter.get_result("job-1")
    assert status == 200
    assert body.startswith(b"BEGIN:VCALENDAR")
    assert headers["Content-Type"] == "text/calendar"
    assert "Content-Disposition" not in headers


def test_get_result_adds_attachment_header_when_download_true():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": {"key": "x"}, "filename": "cal.ics"})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent, \
         patch("app.interface.job.InterfaceApiJob.JobResultLargeStore.load_ref") as load_ref:
        agent.return_value.get.return_value = state
        load_ref.return_value = (b"x", "text/calendar")
        _, _, headers = inter.get_result("job-1", download=True)
    assert "attachment" in headers["Content-Disposition"]
    assert "cal.ics" in headers["Content-Disposition"]


def test_get_result_falls_back_to_job_id_filename_when_missing():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": {"key": "x"}})  # no filename
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent, \
         patch("app.interface.job.InterfaceApiJob.JobResultLargeStore.load_ref") as load_ref:
        agent.return_value.get.return_value = state
        load_ref.return_value = (b"x", "application/octet-stream")
        _, _, headers = inter.get_result("job-1", download=True)
    assert "job-1.bin" in headers["Content-Disposition"]


def test_get_result_returns_not_found_when_state_missing():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = None
        body, _ = inter.get_result("ghost")
    assert body["error_code"] == err.ERROR_JOB_NOT_FOUND.c


def test_get_result_returns_forbidden_when_not_owner():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner="bob")
        body, _ = inter.get_result("job-1")
    assert body["error_code"] == err.ERROR_JOB_FORBIDDEN.c


@pytest.mark.parametrize("status", [JobStatus.PENDING, JobStatus.STARTED, JobStatus.RETRY])
def test_get_result_returns_not_ready_when_state_non_terminal(status):
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(status=status)
        body, _ = inter.get_result("job-1")
    assert body["error_code"] == err.ERROR_JOB_NOT_READY.c


def test_get_result_returns_not_ready_when_state_failed():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(status=JobStatus.FAILURE)
        body, _ = inter.get_result("job-1")
    # FAILURE != SUCCESS so we surface NOT_READY (the result is not downloadable).
    assert body["error_code"] == err.ERROR_JOB_NOT_READY.c


def test_get_result_returns_no_result_when_large_ref_missing():
    inter = InterfaceApiJob(user=_user("alice"))
    # Job succeeded but did not offload anything to the large store.
    state = _state(result={"small_summary": "ok"})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        body, _ = inter.get_result("job-1")
    assert body["error_code"] == err.ERROR_JOB_NO_RESULT.c


def test_get_result_returns_no_result_when_state_result_is_none():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result=None)
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        body, _ = inter.get_result("job-1")
    assert body["error_code"] == err.ERROR_JOB_NO_RESULT.c


@pytest.mark.parametrize("exc", [FileNotFoundError("gone"), ValueError("bad ref"), OSError("io")])
def test_get_result_never_500s_when_store_raises(exc):
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": {"storage": "file", "path": "/x"}})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent, \
         patch("app.interface.job.InterfaceApiJob.JobResultLargeStore.load_ref", side_effect=exc):
        agent.return_value.get.return_value = state
        body, _ = inter.get_result("job-1")
    # A store failure (expired / unreachable file / bad ref) is a clean error, not a 500.
    assert body["error_code"] == err.ERROR_JOB_NO_RESULT.c
    assert body["data"] is None
