"""Unit tests for TaskPersistency — ClientRedis is mocked, no live Redis required."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.agent.AgentConst import TASK_STATE_INDEX_PENDING
from app.agent.tasks.TaskPersistency import TaskPersistency
from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus


_UTC = timezone.utc


def _state(task_id="t-1", user="alice", status=TaskStatus.PENDING) -> TaskState:
    return TaskState(
        task_id=task_id, name="noop", status=status,
        user_uid=user, domain="example.com",
        date_planned=datetime(2026, 5, 26, 10, 0, 0, tzinfo=_UTC),
    )


def _persistency():
    client = MagicMock()
    return TaskPersistency(client, ttl_seconds=3600), client


def test_save_writes_state_and_user_index():
    persistency, client = _persistency()
    persistency.save(_state())
    client.set.assert_called_once()
    args = client.zset_add.call_args_list
    keys = {call.args[0] for call in args}
    assert "taskstate:index:user:alice" in keys
    assert TASK_STATE_INDEX_PENDING in keys


def test_save_terminal_removes_from_pending_index():
    persistency, client = _persistency()
    persistency.save(_state(status=TaskStatus.SUCCESS))
    # User index still maintained, pending dropped.
    assert any(call.args[0] == "taskstate:index:user:alice" for call in client.zset_add.call_args_list)
    client.zset_remove.assert_any_call(TASK_STATE_INDEX_PENDING, "t-1")


def test_get_returns_state_when_present():
    persistency, client = _persistency()
    client.get.return_value = _state().to_dict()
    rebuilt = persistency.get("t-1")
    assert rebuilt is not None
    assert rebuilt.task_id == "t-1"
    assert rebuilt.status == TaskStatus.PENDING


def test_get_returns_none_when_absent():
    persistency, client = _persistency()
    client.get.return_value = None
    assert persistency.get("missing") is None


def test_list_by_user_uses_user_index():
    persistency, client = _persistency()
    client.redis.zrevrange.return_value = [b"t-2", b"t-1"]
    client.get.side_effect = [_state("t-2").to_dict(), _state("t-1").to_dict()]
    result = persistency.list_by_user("alice", limit=10)
    client.redis.zrevrange.assert_called_once_with("taskstate:index:user:alice", 0, 9)
    assert [s.task_id for s in result] == ["t-2", "t-1"]


def test_list_pending_uses_pending_index():
    persistency, client = _persistency()
    client.redis.zrevrange.return_value = []
    persistency.list_pending(limit=50)
    client.redis.zrevrange.assert_called_once_with(TASK_STATE_INDEX_PENDING, 0, 49)


def test_list_skips_expired_entries():
    """Indexes can lag behind TTL expiry; missing TaskState entries are silently skipped."""
    persistency, client = _persistency()
    client.redis.zrevrange.return_value = [b"alive", b"expired"]
    client.get.side_effect = [_state("alive").to_dict(), None]
    result = persistency.list_by_user("alice")
    assert [s.task_id for s in result] == ["alive"]


def test_delete_removes_key_and_both_indexes():
    persistency, client = _persistency()
    client.get.return_value = _state().to_dict()
    persistency.delete("t-1")
    client.delete.assert_called_once_with("taskstate:t-1")
    client.zset_remove.assert_any_call(TASK_STATE_INDEX_PENDING, "t-1")
    client.zset_remove.assert_any_call("taskstate:index:user:alice", "t-1")


def test_save_recurring_task_populates_schedule_index():
    persistency, client = _persistency()
    state = _state()
    state.schedule_name = "imip.scan_inbox"
    persistency.save(state)
    assert any(
        call.args[0] == "taskstate:index:schedule:imip.scan_inbox"
        for call in client.zset_add.call_args_list
    )


def test_list_by_schedule_uses_schedule_index():
    persistency, client = _persistency()
    client.redis.zrevrange.return_value = [b"t-recent", b"t-old"]
    state_recent = _state("t-recent")
    state_recent.schedule_name = "imip.scan_inbox"
    state_old = _state("t-old")
    state_old.schedule_name = "imip.scan_inbox"
    client.get.side_effect = [state_recent.to_dict(), state_old.to_dict()]
    result = persistency.list_by_schedule("imip.scan_inbox", limit=10)
    client.redis.zrevrange.assert_called_once_with("taskstate:index:schedule:imip.scan_inbox", 0, 9)
    assert [s.task_id for s in result] == ["t-recent", "t-old"]


def test_delete_recurring_task_cleans_schedule_index():
    persistency, client = _persistency()
    state = _state()
    state.schedule_name = "imip.scan_inbox"
    client.get.return_value = state.to_dict()
    persistency.delete("t-1")
    client.zset_remove.assert_any_call("taskstate:index:schedule:imip.scan_inbox", "t-1")
