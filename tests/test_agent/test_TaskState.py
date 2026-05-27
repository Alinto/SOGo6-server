"""Unit tests for TaskState serialisation."""
from datetime import datetime, timezone

from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus


_UTC = timezone.utc


def _planned() -> datetime:
    return datetime(2026, 5, 26, 10, 0, 0, tzinfo=_UTC)


def test_round_trip_preserves_all_fields():
    state = TaskState(
        task_id="t-1", name="noop", status=TaskStatus.STARTED,
        user_uid="alice", domain="example.com",
        date_planned=_planned(),
        date_start=datetime(2026, 5, 26, 10, 0, 5, tzinfo=_UTC),
        date_end=datetime(2026, 5, 26, 10, 1, 5, tzinfo=_UTC),
        duration_seconds=60.0, attempts=1, max_retry=3,
        payload={"foo": "bar"}, result={"ok": True}, error=None,
    )
    rebuilt = TaskState.from_dict(state.to_dict())
    assert rebuilt == state


def test_round_trip_handles_optional_datetimes():
    state = TaskState(
        task_id="t-2", name="noop", status=TaskStatus.PENDING,
        user_uid="alice", domain="example.com",
        date_planned=_planned(),
    )
    rebuilt = TaskState.from_dict(state.to_dict())
    assert rebuilt.date_start is None
    assert rebuilt.date_end is None
    assert rebuilt.duration_seconds is None


def test_is_terminal():
    assert TaskStatus.is_terminal(TaskStatus.SUCCESS)
    assert TaskStatus.is_terminal(TaskStatus.FAILURE)
    assert TaskStatus.is_terminal(TaskStatus.CANCELED)
    assert not TaskStatus.is_terminal(TaskStatus.PENDING)
    assert not TaskStatus.is_terminal(TaskStatus.STARTED)
    assert not TaskStatus.is_terminal(TaskStatus.RETRY)
