"""Unit tests for TaskRecovery — agent, persistency and cache are mocked."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.agent.tasks.TaskRecovery import TaskRecovery
from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus


def _state(*, task_id="t-1", name="example", status=TaskStatus.STARTED, attempts=1, max_try=3) -> TaskState:
    return TaskState(
        task_id=task_id, name=name, status=status, user_uid="alice",
        date_planned=datetime(2026, 5, 29, 10, 0, 0, tzinfo=timezone.utc),
        date_start=datetime(2026, 5, 29, 10, 0, 5, tzinfo=timezone.utc),
        attempts=attempts, max_try=max_try,
    )


def _task(*, resume=True):
    t = MagicMock()
    t.request_class.resume = resume
    return t


def _recovery():
    agent = MagicMock()
    persistency = MagicMock()
    cache = MagicMock()
    cache.set.return_value = True  # lock acquired by default
    return TaskRecovery(agent, persistency, cache), agent, persistency, cache


def test_resume_eligible_task_is_requeued():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state(attempts=1, max_try=3)]
    agent.get_task.return_value = _task(resume=True)
    assert recovery.reconcile_orphans() == (1, 0)
    agent.create_task.assert_called_once()
    saved = persistency.save.call_args.args[0]
    assert saved.status == TaskStatus.PENDING
    assert saved.date_start is None


def test_resume_false_marks_task_failure():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state()]
    agent.get_task.return_value = _task(resume=False)
    assert recovery.reconcile_orphans() == (0, 1)
    agent.create_task.assert_not_called()
    saved = persistency.save.call_args.args[0]
    assert saved.status == TaskStatus.FAILURE


def test_attempts_exhausted_marks_failure():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state(attempts=3, max_try=3)]
    agent.get_task.return_value = _task(resume=True)
    assert recovery.reconcile_orphans() == (0, 1)


def test_unknown_task_marks_failure():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state()]
    agent.get_task.return_value = None
    assert recovery.reconcile_orphans() == (0, 1)


def test_terminal_states_are_left_alone():
    recovery, _, persistency, _ = _recovery()
    persistency.list_pending.return_value = [
        _state(task_id="t-ok", status=TaskStatus.SUCCESS),
        _state(task_id="t-ko", status=TaskStatus.FAILURE),
        _state(task_id="t-cancel", status=TaskStatus.CANCELED),
    ]
    assert recovery.reconcile_orphans() == (0, 0)
    persistency.save.assert_not_called()


def test_returns_zero_when_lock_already_held():
    recovery, _, persistency, cache = _recovery()
    cache.set.return_value = False  # another worker holds the lock
    assert recovery.reconcile_orphans() == (0, 0)
    persistency.list_pending.assert_not_called()
