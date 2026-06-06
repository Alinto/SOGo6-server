"""Unit tests for JobStateSerializerDict (JobState -> public API dict)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus
from app.agent.jobs.serializer.JobStateSerializerDict import JobStateSerializerDict

_UTC = timezone.utc


def _state(*, name="calendar.export.ics", payload=None, result=None):
    return JobState(
        job_id="job-1", name=name, status=JobStatus.SUCCESS, user_uid="alice",
        date_planned=datetime(2026, 6, 1, tzinfo=_UTC),
        payload=payload or {}, result=result,
    )


def _agent(handler=None):
    agent = MagicMock()
    agent.get_job_handler.return_value = handler
    return agent


def test_exposes_only_public_fields():
    # The serializer IS the public view: no internal field (job_id, name, user_uid,
    # dates, attempts...) must leak, regardless of what JobState holds.
    out = JobStateSerializerDict(_agent(None)).serialize(_state(payload={"k": "v"}, result={"n": 1}))
    assert set(out.keys()) == {"status", "payload", "result", "error"}
    assert out["status"] == "success"


def test_redacts_payload_through_handler():
    handler = MagicMock()
    handler.public_payload.return_value = {"calendar_key": "cal-1"}  # token stripped
    out = JobStateSerializerDict(_agent(handler)).serialize(
        _state(payload={"calendar_key": "cal-1", "token": "secret"})
    )
    handler.public_payload.assert_called_once_with({"calendar_key": "cal-1", "token": "secret"})
    assert out["payload"] == {"calendar_key": "cal-1"}


def test_keeps_payload_when_handler_unknown():
    out = JobStateSerializerDict(_agent(None)).serialize(_state(payload={"calendar_key": "cal-1"}))
    assert out["payload"] == {"calendar_key": "cal-1"}


def test_strips_large_result_pointer_but_keeps_other_result_fields():
    out = JobStateSerializerDict(_agent(None)).serialize(
        _state(result={"large_result": {"storage": "file", "locator": "/x"}, "filename": "cal.ics"})
    )
    assert "large_result" not in out["result"]
    assert out["result"]["filename"] == "cal.ics"


def test_inline_result_passes_through_untouched():
    # An import job returns small counters inline - nothing to strip.
    counters = {"inserted": 3, "updated": 1, "deleted": 0}
    out = JobStateSerializerDict(_agent(None)).serialize(_state(result=counters))
    assert out["result"] == counters
