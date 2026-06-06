"""Unit tests for the ClientAgent manager facade."""
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.agent.jobs.JobRequest import JobRequest
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus
from app.agent.jobs.job_large_store.JobLargeStorage import JobLargeStorage
from app.manager.agent.ClientAgent import ClientAgent
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _build():
    agent = MagicMock()
    persistency = MagicMock()
    canceller = MagicMock()
    cache = MagicMock()
    cache.set.return_value = True
    client = ClientAgent(agent, persistency, canceller, cache, JobLargeStorage.FILE)
    return client, agent, persistency, canceller, cache


def _req(
    name: str,
    body: dict[str, Any] | None = None,
    *,
    max_try: int = 1,
    soft_timeout_seconds: int = 300,
    resume: bool = True,
    max_concurrent: int = 0,
) -> JobRequest:
    req = MagicMock()
    req.name = name
    req.max_try = max_try
    req.soft_timeout_seconds = soft_timeout_seconds
    req.resume = resume
    req.max_concurrent = max_concurrent
    req.payload.return_value = body or {}
    return req


def test_enqueue_persists_pending_state_before_sending_to_the_broker():
    client, agent, persistency, _, _ = _build()
    calls: list[str] = []
    persistency.save.side_effect = lambda *a, **kw: calls.append("save")
    agent.create_job.side_effect = lambda *a, **kw: calls.append("create_task") or "ignored"

    job_id = client.enqueue(_req("imip.send", {"to": "bob"}), user_uid="alice")

    assert calls == ["save", "create_task"]
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.job_id == job_id
    assert saved.name == "imip.send"
    assert saved.status == JobStatus.PENDING
    assert saved.user_uid == "alice"
    assert saved.payload == {"to": "bob"}
    assert agent.create_job.call_args.kwargs["job_id"] == job_id


def test_enqueue_system_task_has_no_user_uid():
    client, agent, _, _, _ = _build()
    client.enqueue(_req("admin.purge"))
    assert agent.create_job.call_args.kwargs["user_uid"] is None


def test_enqueue_forwards_eta_to_the_broker():
    client, agent, _, _, _ = _build()
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    client.enqueue(_req("imip.send"), user_uid="alice", eta=when)
    assert agent.create_job.call_args.kwargs["eta"] == when


def test_start_is_enqueue_with_an_immediate_eta():
    client, agent, _, _, _ = _build()
    before = datetime.now(timezone.utc)
    client.start(_req("imip.send", {"to": "bob"}), user_uid="alice")
    after = datetime.now(timezone.utc)
    assert before <= agent.create_job.call_args.kwargs["eta"] <= after


def test_get_delegates_to_persistency():
    client, _, persistency, _, _ = _build()
    expected = JobState(
        job_id="t-1", name="example", status=JobStatus.PENDING, user_uid="alice",
        date_planned=datetime.now(timezone.utc),
    )
    persistency.get.return_value = expected
    assert client.get("t-1") is expected


def test_get_returns_none_for_expired_state():
    client, _, persistency, _, _ = _build()
    persistency.get.return_value = None
    assert client.get("ghost") is None


def test_cancel_delegates_to_the_canceller():
    client, _, _, canceller, _ = _build()
    client.cancel("t-1")
    canceller.cancel.assert_called_once_with("t-1")


def test_list_methods_forward_to_persistency():
    client, _, persistency, _, _ = _build()
    client.list_by_user("alice", limit=20)
    client.list_pending(limit=50)
    client.list_by_schedule("imip.scan_inbox", limit=5)
    persistency.list_by_user.assert_called_once_with("alice", limit=20)
    persistency.list_pending.assert_called_once_with(limit=50)
    persistency.list_by_schedule.assert_called_once_with("imip.scan_inbox", limit=5)


def test_enqueue_copies_metadata_from_the_request():
    client, _, persistency, _, _ = _build()
    client.enqueue(_req("imip.send", max_try=5, soft_timeout_seconds=120, max_concurrent=1))
    saved: JobState = persistency.save.call_args.args[0]
    assert saved.max_try == 5
    assert saved.soft_timeout_seconds == 120
    assert saved.max_concurrent == 1


def test_get_marks_zombie_started_task_as_failure():
    client, _, persistency, _, _ = _build()
    long_ago = datetime.now(timezone.utc).timestamp() - 7200
    state = JobState(
        job_id="z-1", name="system.test", status=JobStatus.STARTED, user_uid="alice",
        date_planned=datetime.now(timezone.utc),
        date_start=datetime.fromtimestamp(long_ago, tz=timezone.utc),
        soft_timeout_seconds=60,
    )
    persistency.get.return_value = state

    result = client.get("z-1")
    assert result is not None
    assert result.status == JobStatus.FAILURE
    assert "interrupted" in (result.error or "").lower()
    persistency.save.assert_called()


def test_get_keeps_recent_started_task_alone():
    client, _, persistency, _, _ = _build()
    state = JobState(
        job_id="ok-1", name="system.test", status=JobStatus.STARTED, user_uid="alice",
        date_planned=datetime.now(timezone.utc),
        date_start=datetime.now(timezone.utc),
        soft_timeout_seconds=60,
    )
    persistency.get.return_value = state
    assert client.get("ok-1").status == JobStatus.STARTED


# ========== Concurrency gate ==========

def test_enqueue_acquires_concurrency_lock_when_max_concurrent_is_one():
    client, _, _, _, cache = _build()
    client.enqueue(_req("imip.send", max_concurrent=1), user_uid="alice")
    cache.set.assert_called_once()
    args, kwargs = cache.set.call_args
    assert args[0] == JobState.concurrency_lock_key("imip.send", "alice")
    assert kwargs.get("nx") is True


def test_enqueue_skips_lock_when_max_concurrent_is_zero():
    client, _, _, _, cache = _build()
    client.enqueue(_req("system.purge", max_concurrent=0))
    cache.set.assert_not_called()


def test_enqueue_raises_concurrent_limit_when_lock_held():
    client, agent, persistency, _, cache = _build()
    cache.set.return_value = False  # SET NX fails because another job holds the lock
    with pytest.raises(RequestException) as exc:
        client.enqueue(_req("imip.send", max_concurrent=1), user_uid="alice")
    assert exc.value.error == err.ERROR_JOB_CONCURRENT_LIMIT
    persistency.save.assert_not_called()
    agent.create_job.assert_not_called()


def test_enqueue_releases_lock_when_broker_publish_fails():
    client, agent, _, _, cache = _build()
    agent.create_job.side_effect = RuntimeError("broker down")
    with pytest.raises(RuntimeError):
        client.enqueue(_req("imip.send", max_concurrent=1), user_uid="alice")
    cache.delete.assert_called_once_with(JobState.concurrency_lock_key("imip.send", "alice"))


def test_enqueue_uses_global_scope_when_no_user():
    client, _, _, _, cache = _build()
    client.enqueue(_req("system.purge", max_concurrent=1))
    assert cache.set.call_args.args[0] == JobState.concurrency_lock_key("system.purge", None)


def test_enqueue_raises_for_unsupported_max_concurrent_gt_one():
    client, _, _, _, _ = _build()
    with pytest.raises(NotImplementedError):
        client.enqueue(_req("imip.send", max_concurrent=2), user_uid="alice")
