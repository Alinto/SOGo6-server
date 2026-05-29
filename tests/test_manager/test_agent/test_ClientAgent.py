"""Unit tests for the ClientAgent manager façade."""
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from app.agent.tasks.TaskRequest import TaskRequest
from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus
from app.manager.agent.ClientAgent import ClientAgent


def _build():
    agent = MagicMock()
    persistency = MagicMock()
    canceller = MagicMock()
    return ClientAgent(agent, persistency, canceller), agent, persistency, canceller


def _req(
    name: str,
    body: dict[str, Any] | None = None,
    *,
    max_try: int = 1,
    soft_timeout_seconds: int = 300,
    resume: bool = True,
) -> TaskRequest:
    req = MagicMock()
    req.name = name
    req.max_try = max_try
    req.soft_timeout_seconds = soft_timeout_seconds
    req.resume = resume
    req.payload.return_value = body or {}
    return req


def test_enqueue_persists_pending_state_before_sending_to_the_broker():
    client, agent, persistency, _ = _build()
    calls: list[str] = []
    persistency.save.side_effect = lambda *a, **kw: calls.append("save")
    agent.create_task.side_effect = lambda *a, **kw: calls.append("create_task") or "ignored"

    task_id = client.enqueue(_req("imip.send", {"to": "bob"}), user_uid="alice")

    assert calls == ["save", "create_task"]
    saved: TaskState = persistency.save.call_args.args[0]
    assert saved.task_id == task_id
    assert saved.name == "imip.send"
    assert saved.status == TaskStatus.PENDING
    assert saved.user_uid == "alice"
    assert saved.payload == {"to": "bob"}
    assert agent.create_task.call_args.kwargs["task_id"] == task_id


def test_enqueue_system_task_has_no_user_uid():
    client, agent, _, _ = _build()
    client.enqueue(_req("admin.purge"))
    assert agent.create_task.call_args.kwargs["user_uid"] is None


def test_enqueue_forwards_eta_to_the_broker():
    client, agent, _, _ = _build()
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    client.enqueue(_req("imip.send"), user_uid="alice", eta=when)
    assert agent.create_task.call_args.kwargs["eta"] == when


def test_start_is_enqueue_with_an_immediate_eta():
    client, agent, _, _ = _build()
    before = datetime.now(timezone.utc)
    client.start(_req("imip.send", {"to": "bob"}), user_uid="alice")
    after = datetime.now(timezone.utc)
    assert before <= agent.create_task.call_args.kwargs["eta"] <= after


def test_get_delegates_to_persistency():
    client, _, persistency, _ = _build()
    expected = TaskState(
        task_id="t-1", name="example", status=TaskStatus.PENDING, user_uid="alice",
        date_planned=datetime.now(timezone.utc),
    )
    persistency.get.return_value = expected
    assert client.get("t-1") is expected


def test_get_returns_none_for_expired_state():
    client, _, persistency, _ = _build()
    persistency.get.return_value = None
    assert client.get("ghost") is None


def test_cancel_delegates_to_the_canceller():
    client, _, _, canceller = _build()
    client.cancel("t-1")
    canceller.cancel.assert_called_once_with("t-1")


def test_list_methods_forward_to_persistency():
    client, _, persistency, _ = _build()
    client.list_by_user("alice", limit=20)
    client.list_pending(limit=50)
    client.list_by_schedule("imip.scan_inbox", limit=5)
    persistency.list_by_user.assert_called_once_with("alice", limit=20)
    persistency.list_pending.assert_called_once_with(limit=50)
    persistency.list_by_schedule.assert_called_once_with("imip.scan_inbox", limit=5)


def test_enqueue_copies_metadata_from_the_request():
    client, _, persistency, _ = _build()
    client.enqueue(_req("imip.send", max_try=5, soft_timeout_seconds=120))
    saved: TaskState = persistency.save.call_args.args[0]
    assert saved.max_try == 5
    assert saved.soft_timeout_seconds == 120


def test_get_marks_zombie_started_task_as_failure():
    client, _, persistency, _ = _build()
    long_ago = datetime.now(timezone.utc).timestamp() - 7200
    state = TaskState(
        task_id="z-1", name="system.test", status=TaskStatus.STARTED, user_uid="alice",
        date_planned=datetime.now(timezone.utc),
        date_start=datetime.fromtimestamp(long_ago, tz=timezone.utc),
        soft_timeout_seconds=60,
    )
    persistency.get.return_value = state

    result = client.get("z-1")
    assert result is not None
    assert result.status == TaskStatus.FAILURE
    assert "interrupted" in (result.error or "").lower()
    persistency.save.assert_called()


def test_get_keeps_recent_started_task_alone():
    client, _, persistency, _ = _build()
    state = TaskState(
        task_id="ok-1", name="system.test", status=TaskStatus.STARTED, user_uid="alice",
        date_planned=datetime.now(timezone.utc),
        date_start=datetime.now(timezone.utc),
        soft_timeout_seconds=60,
    )
    persistency.get.return_value = state
    assert client.get("ok-1").status == TaskStatus.STARTED
