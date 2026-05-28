"""Unit tests for AgentApp.register_lifecycle_hooks.

We trigger the Celery signals manually with the same kwargs Celery would supply at
runtime and assert that TaskPersistency receives the right state transitions. No real
worker, no real broker — pure signal plumbing.

Hooks are connected once at module load (Celery's signal registry is global, so connecting
in every fixture would multiply handlers across tests). Each test resets and reconfigures
the same MagicMock.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from celery.signals import task_failure, task_postrun, task_prerun, task_revoked

from app.agent.AgentApp import agent
from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus


_UTC = timezone.utc
_PERSISTENCY: MagicMock = MagicMock()
agent.register_lifecycle_hooks(_PERSISTENCY)


def _state(status=TaskStatus.PENDING) -> TaskState:
    return TaskState(
        task_id="t-1", name="noop", status=status,
        user_uid="alice",
        date_planned=datetime(2026, 5, 27, 10, 0, 0, tzinfo=_UTC),
    )


@pytest.fixture
def persistency():
    _PERSISTENCY.reset_mock()
    return _PERSISTENCY


def test_prerun_marks_state_as_started(persistency):
    persistency.get.return_value = _state(status=TaskStatus.PENDING)
    task_prerun.send(sender=None, task_id="t-1")
    saved: TaskState = persistency.save.call_args.args[0]
    assert saved.status == TaskStatus.STARTED
    assert saved.date_start is not None
    assert saved.attempts == 1


def test_postrun_success_records_result_and_duration(persistency):
    state = _state(status=TaskStatus.STARTED)
    state.date_start = datetime.now(_UTC)
    persistency.get.return_value = state
    task_postrun.send(sender=None, task_id="t-1", state="SUCCESS", retval={"echo": "ok"})
    saved: TaskState = persistency.save.call_args.args[0]
    assert saved.status == TaskStatus.SUCCESS
    assert saved.result == {"echo": "ok"}
    assert saved.duration_seconds is not None and saved.duration_seconds >= 0


def test_failure_records_error_message(persistency):
    persistency.get.return_value = _state(status=TaskStatus.STARTED)
    task_failure.send(sender=None, task_id="t-1", exception=RuntimeError("boom"))
    saved: TaskState = persistency.save.call_args.args[0]
    assert saved.status == TaskStatus.FAILURE
    assert saved.error == "boom"


def test_revoked_marks_state_as_canceled(persistency):
    state = _state(status=TaskStatus.STARTED)
    state.date_start = datetime.now(_UTC)
    persistency.get.return_value = state
    task_revoked.send(sender=None, request=SimpleNamespace(id="t-1"))
    saved: TaskState = persistency.save.call_args.args[0]
    assert saved.status == TaskStatus.CANCELED
    assert saved.date_end is not None


def test_signal_for_unknown_task_id_is_silent(persistency):
    """A signal for a TaskState that has been TTL-expired must not crash the hook."""
    persistency.get.return_value = None
    task_prerun.send(sender=None, task_id="ghost")
    persistency.save.assert_not_called()
