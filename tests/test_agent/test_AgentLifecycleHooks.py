"""Unit tests for Agent.register_lifecycle_hooks.

We trigger the Celery signals manually with the same kwargs Celery would supply at
runtime and assert that JobPersistency receives the right state transitions. No real
worker, no real broker - pure signal plumbing.

Hooks are connected once at module load (Celery's signal registry is global, so connecting
in every fixture would multiply handlers across tests). Each test resets and reconfigures
the same MagicMock.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from celery.signals import task_failure, task_postrun, task_prerun, task_retry, task_revoked

from app.agent.Agent import agent
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus


_UTC = timezone.utc
_PERSISTENCY: MagicMock = MagicMock()
_CACHE: MagicMock = MagicMock()
agent.register_lifecycle_hooks(_PERSISTENCY, _CACHE)


def _state(status=JobStatus.PENDING, max_concurrent=0) -> JobState:
    return JobState(
        job_id="t-1", name="example", status=status,
        user_uid="alice",
        date_planned=datetime(2026, 5, 27, 10, 0, 0, tzinfo=_UTC),
        max_concurrent=max_concurrent,
    )


@pytest.fixture
def persistency():
    _PERSISTENCY.reset_mock()
    return _PERSISTENCY


@pytest.fixture
def cache():
    _CACHE.reset_mock()
    return _CACHE


def test_prerun_marks_state_as_started(persistency):
    persistency.get.return_value = _state(status=JobStatus.PENDING)
    task_prerun.send(sender=None, task_id="t-1")
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.STARTED
    assert saved.date_start is not None
    assert saved.attempts == 1


def test_postrun_success_records_result_and_duration(persistency):
    state = _state(status=JobStatus.STARTED)
    state.date_start = datetime.now(_UTC)
    persistency.get.return_value = state
    task_postrun.send(sender=None, task_id="t-1", state="SUCCESS", retval={"echo": "ok"})
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.SUCCESS
    assert saved.result == {"echo": "ok"}
    assert saved.duration_seconds is not None and saved.duration_seconds >= 0


def test_failure_marks_state_as_failure(persistency):
    """Celery only fires task_failure after retries are exhausted."""
    state = _state(status=JobStatus.STARTED)
    persistency.get.return_value = state
    task_failure.send(sender=None, task_id="t-1", exception=RuntimeError("boom"))
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.FAILURE
    assert saved.error == "boom"


def test_retry_marks_state_as_retry(persistency):
    state = _state(status=JobStatus.STARTED)
    persistency.get.return_value = state
    task_retry.send(
        sender=None, request=SimpleNamespace(id="t-1"), reason=RuntimeError("transient"),
    )
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.RETRY
    assert saved.error == "transient"


def test_postrun_with_retry_state_does_nothing(persistency):
    """Celery sends postrun with state='RETRY' between attempts; the hook must not
    overwrite the RETRY status set by task_retry."""
    state = _state(status=JobStatus.RETRY)
    persistency.get.return_value = state
    task_postrun.send(sender=None, task_id="t-1", state="RETRY", retval=None)
    persistency.save.assert_not_called()


def test_revoked_marks_state_as_canceled(persistency):
    state = _state(status=JobStatus.STARTED)
    state.date_start = datetime.now(_UTC)
    persistency.get.return_value = state
    task_revoked.send(sender=None, request=SimpleNamespace(id="t-1"))
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.status == JobStatus.CANCELED
    assert saved.date_end is not None


def test_signal_for_unknown_job_id_is_silent(persistency):
    """A signal for a JobState that has been TTL-expired must not crash the hook."""
    persistency.get.return_value = None
    task_prerun.send(sender=None, task_id="ghost")
    persistency.save.assert_not_called()


def test_terminal_hook_releases_lock_when_max_concurrent_set(persistency, cache):
    persistency.get.return_value = _state(status=JobStatus.STARTED, max_concurrent=1)
    task_postrun.send(sender=None, task_id="t-1", state="SUCCESS", retval={})
    cache.delete.assert_called_once_with(JobState.concurrency_lock_key("example", "alice"))


def test_terminal_hook_skips_release_when_no_concurrency_gate(persistency, cache):
    # max_concurrent=0 -> no lock was ever taken, so nothing to delete.
    persistency.get.return_value = _state(status=JobStatus.STARTED, max_concurrent=0)
    task_postrun.send(sender=None, task_id="t-1", state="SUCCESS", retval={})
    cache.delete.assert_not_called()
