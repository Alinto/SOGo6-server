"""Unit tests for JobRecovery — agent, persistency and cache are mocked."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.agent.jobs.JobRecovery import JobRecovery
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus


def _state(*, job_id="t-1", name="example", status=JobStatus.STARTED, attempts=1, max_try=3) -> JobState:
    return JobState(
        job_id=job_id, name=name, status=status, user_uid="alice",
        date_planned=datetime(2026, 5, 29, 10, 0, 0, tzinfo=timezone.utc),
        date_start=datetime(2026, 5, 29, 10, 0, 5, tzinfo=timezone.utc),
        attempts=attempts, max_try=max_try,
    )


def _handler(*, resume=True):
    h = MagicMock()
    h.request_class.resume = resume
    return h


def _recovery():
    agent = MagicMock()
    persistency = MagicMock()
    cache = MagicMock()
    cache.set.return_value = True  # lock acquired by default
    return JobRecovery(agent, persistency, cache), agent, persistency, cache


def test_resume_eligible_job_is_requeued():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state(attempts=1, max_try=3)]
    agent.get_job_handler.return_value = _handler(resume=True)
    assert recovery.reconcile_orphans() == (1, 0)
    agent.create_job.assert_called_once()
    saved = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.PENDING
    assert saved.date_start is None


def test_resume_false_marks_job_failure():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state()]
    agent.get_job_handler.return_value = _handler(resume=False)
    assert recovery.reconcile_orphans() == (0, 1)
    agent.create_job.assert_not_called()
    saved = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.FAILURE


def test_failure_releases_concurrency_lock():
    recovery, agent, persistency, cache = _recovery()
    persistency.list_pending.return_value = [_state(name="calendar.export.ics")]
    agent.get_job_handler.return_value = _handler(resume=False)
    recovery.reconcile_orphans()
    # No lifecycle hook fires for a manually-failed orphan, so JobRecovery must
    # release the concurrency lock itself, or the user stays blocked until the TTL.
    cache.delete.assert_called_once_with(
        JobState.concurrency_lock_key("calendar.export.ics", "alice"),
    )


def test_resume_does_not_release_concurrency_lock():
    recovery, agent, persistency, cache = _recovery()
    persistency.list_pending.return_value = [_state(attempts=1, max_try=3)]
    agent.get_job_handler.return_value = _handler(resume=True)
    recovery.reconcile_orphans()
    # A resumed job is still in flight — its lock must stay held.
    cache.delete.assert_not_called()


def test_attempts_exhausted_marks_failure():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state(attempts=3, max_try=3)]
    agent.get_job_handler.return_value = _handler(resume=True)
    assert recovery.reconcile_orphans() == (0, 1)


def test_unknown_job_marks_failure():
    recovery, agent, persistency, _ = _recovery()
    persistency.list_pending.return_value = [_state()]
    agent.get_job_handler.return_value = None
    assert recovery.reconcile_orphans() == (0, 1)


def test_terminal_states_are_left_alone():
    recovery, _, persistency, _ = _recovery()
    persistency.list_pending.return_value = [
        _state(job_id="t-ok", status=JobStatus.SUCCESS),
        _state(job_id="t-ko", status=JobStatus.FAILURE),
        _state(job_id="t-cancel", status=JobStatus.CANCELED),
    ]
    assert recovery.reconcile_orphans() == (0, 0)
    persistency.save.assert_not_called()


def test_returns_zero_when_lock_already_held():
    recovery, _, persistency, cache = _recovery()
    cache.set.return_value = False  # another worker holds the lock
    assert recovery.reconcile_orphans() == (0, 0)
    persistency.list_pending.assert_not_called()
