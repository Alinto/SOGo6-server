"""Unit tests for JobState serialisation."""
from datetime import datetime, timezone

from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus


_UTC = timezone.utc


def _planned() -> datetime:
    return datetime(2026, 5, 26, 10, 0, 0, tzinfo=_UTC)


def test_round_trip_preserves_all_fields():
    state = JobState(
        job_id="t-1", name="example", status=JobStatus.STARTED,
        user_uid="alice",
        date_planned=_planned(),
        date_start=datetime(2026, 5, 26, 10, 0, 5, tzinfo=_UTC),
        date_end=datetime(2026, 5, 26, 10, 1, 5, tzinfo=_UTC),
        duration_seconds=60.0, attempts=1, max_try=3, max_concurrent=2,
        payload={"foo": "bar"}, result={"ok": True}, error=None,
    )
    rebuilt = JobState.from_dict(state.to_dict())
    assert rebuilt == state
    assert rebuilt.max_concurrent == 2


def test_round_trip_handles_optional_datetimes():
    state = JobState(
        job_id="t-2", name="example", status=JobStatus.PENDING,
        user_uid="alice",
        date_planned=_planned(),
    )
    rebuilt = JobState.from_dict(state.to_dict())
    assert rebuilt.date_start is None
    assert rebuilt.date_end is None
    assert rebuilt.duration_seconds is None


def test_is_terminal():
    assert JobStatus.is_terminal(JobStatus.SUCCESS)
    assert JobStatus.is_terminal(JobStatus.FAILURE)
    assert JobStatus.is_terminal(JobStatus.CANCELED)
    assert not JobStatus.is_terminal(JobStatus.PENDING)
    assert not JobStatus.is_terminal(JobStatus.STARTED)
    assert not JobStatus.is_terminal(JobStatus.RETRY)
