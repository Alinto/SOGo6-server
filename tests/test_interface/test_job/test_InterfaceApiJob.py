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
    # Only public fields are exposed - never internal ones (user_uid, job_id, name, dates...).
    assert set(body["data"].keys()) == {"status", "payload", "result", "error"}
    assert "user_uid" not in body["data"]


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


def test_get_job_forbids_system_job_even_for_a_user():
    # A system job (user_uid=None) belongs to no user and must never be exposed,
    # even though None != "alice" already; the explicit guard is defence in depth.
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner=None)
        body, _ = inter.get_job("job-1")
    assert body["error_code"] == err.ERROR_JOB_FORBIDDEN.c


def test_get_result_forbids_system_job():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner=None)
        body, _ = inter.get_result("job-1")
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


# ========== cancel_job ==========

def test_cancel_job_calls_canceller_and_returns_refreshed_state():
    inter = InterfaceApiJob(user=_user("alice"))
    running = _state(owner="alice", status=JobStatus.STARTED)
    canceled = _state(owner="alice", status=JobStatus.CANCELED)
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.side_effect = [running, canceled]  # before, then after cancel
        agent.return_value.get_job_handler.return_value = None
        body, status = inter.cancel_job("job-1")
    agent.return_value.cancel.assert_called_once_with("job-1")
    assert status == 200
    assert body["data"]["status"] == "canceled"


def test_cancel_job_returns_not_found_when_unknown():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = None
        body, _ = inter.cancel_job("ghost")
    agent.return_value.cancel.assert_not_called()
    assert body["error_code"] == err.ERROR_JOB_NOT_FOUND.c


def test_cancel_job_forbidden_when_not_owner():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner="bob")
        body, _ = inter.cancel_job("job-1")
    agent.return_value.cancel.assert_not_called()
    assert body["error_code"] == err.ERROR_JOB_FORBIDDEN.c


def test_cancel_job_forbids_system_job():
    inter = InterfaceApiJob(user=_user("alice"))
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = _state(owner=None)
        body, _ = inter.cancel_job("job-1")
    agent.return_value.cancel.assert_not_called()
    assert body["error_code"] == err.ERROR_JOB_FORBIDDEN.c


# ========== get_result ==========

def _ref(content_type="text/calendar", locator="x"):
    return {"content_type": content_type, "locator": locator}


def test_get_result_streams_blob_with_native_content_type():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": _ref("text/calendar"), "filename": "cal.ics"})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        agent.return_value.get_large_store.return_value.load.return_value = b"BEGIN:VCALENDAR\r\n"
        body, status, headers = inter.get_result("job-1")
    assert status == 200
    assert body.startswith(b"BEGIN:VCALENDAR")
    assert headers["Content-Type"] == "text/calendar"   # from the ref, not the blob
    assert "Content-Disposition" not in headers


def test_get_result_adds_attachment_header_when_download_true():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": _ref(), "filename": "cal.ics"})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        agent.return_value.get_large_store.return_value.load.return_value = b"x"
        _, _, headers = inter.get_result("job-1", download=True)
    assert "attachment" in headers["Content-Disposition"]
    assert "cal.ics" in headers["Content-Disposition"]


def test_get_result_falls_back_to_job_id_filename_when_missing():
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": _ref("application/octet-stream")})  # no filename
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        agent.return_value.get_large_store.return_value.load.return_value = b"x"
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
    state = _state(result={"large_result": _ref(locator="/x")})
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        agent.return_value.get_large_store.return_value.load.side_effect = exc
        body, _ = inter.get_result("job-1")
    # A store failure (expired / unreachable file / bad ref) is a clean error, not a 500.
    assert body["error_code"] == err.ERROR_JOB_NO_RESULT.c
    assert body["data"] is None


def test_get_result_returns_no_result_on_malformed_ref():
    # A stored large_result missing a key -> JobLargeRef.from_dict raises KeyError ->
    # must surface a clean 410, never a 500.
    inter = InterfaceApiJob(user=_user("alice"))
    state = _state(result={"large_result": {"locator": "/x"}})  # no content_type
    with patch("app.interface.job.InterfaceApiJob.sogo_agent") as agent:
        agent.return_value.get.return_value = state
        body, _ = inter.get_result("job-1")
    assert body["error_code"] == err.ERROR_JOB_NO_RESULT.c
