"""Unit tests for JobPersistency — ClientRedis is mocked, no live Redis required."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.agent.AgentConst import JOB_STATE_INDEX_PENDING
from app.agent.jobs.JobPersistency import JobPersistency
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus


_UTC = timezone.utc


def _state(job_id="t-1", user="alice", status=JobStatus.PENDING) -> JobState:
    return JobState(
        job_id=job_id, name="example", status=status,
        user_uid=user,
        date_planned=datetime(2026, 5, 26, 10, 0, 0, tzinfo=_UTC),
    )


def _persistency():
    client = MagicMock()
    return JobPersistency(client, ttl_seconds=3600), client


def test_save_writes_state_and_user_index():
    persistency, client = _persistency()
    persistency.save(_state())
    client.set.assert_called_once()
    args = client.zset_add.call_args_list
    keys = {call.args[0] for call in args}
    assert "jobstate:index:user:alice" in keys
    assert JOB_STATE_INDEX_PENDING in keys


def test_save_terminal_removes_from_pending_index():
    persistency, client = _persistency()
    persistency.save(_state(status=JobStatus.SUCCESS))
    # User index still maintained, pending dropped.
    assert any(call.args[0] == "jobstate:index:user:alice" for call in client.zset_add.call_args_list)
    client.zset_remove.assert_any_call(JOB_STATE_INDEX_PENDING, "t-1")


def test_get_returns_state_when_present():
    persistency, client = _persistency()
    client.get.return_value = _state().to_dict()
    rebuilt = persistency.get("t-1")
    assert rebuilt is not None
    assert rebuilt.job_id == "t-1"
    assert rebuilt.status == JobStatus.PENDING


def test_get_returns_none_when_absent():
    persistency, client = _persistency()
    client.get.return_value = None
    assert persistency.get("missing") is None


def test_list_by_user_uses_user_index():
    persistency, client = _persistency()
    client.zset_revrange.return_value = ["t-2", "t-1"]
    client.get.side_effect = [_state("t-2").to_dict(), _state("t-1").to_dict()]
    result = persistency.list_by_user("alice", limit=10)
    client.zset_revrange.assert_called_once_with("jobstate:index:user:alice", 0, 9)
    assert [s.job_id for s in result] == ["t-2", "t-1"]


def test_list_pending_uses_pending_index():
    persistency, client = _persistency()
    client.zset_revrange.return_value = []
    persistency.list_pending(limit=50)
    client.zset_revrange.assert_called_once_with(JOB_STATE_INDEX_PENDING, 0, 49)


def test_list_skips_and_prunes_expired_entries():
    """Indexes lag behind TTL expiry; missing entries are skipped AND pruned from the index."""
    persistency, client = _persistency()
    client.zset_revrange.return_value = ["alive", "expired"]
    client.get.side_effect = [_state("alive").to_dict(), None]
    result = persistency.list_by_user("alice")
    assert [s.job_id for s in result] == ["alive"]
    # The dangling id must be removed from the user index so it cannot grow unbounded.
    client.zset_remove.assert_any_call("jobstate:index:user:alice", "expired")


def test_list_does_not_prune_when_all_entries_alive():
    persistency, client = _persistency()
    client.zset_revrange.return_value = ["t-1"]
    client.get.side_effect = [_state("t-1").to_dict()]
    persistency.list_by_user("alice")
    client.zset_remove.assert_not_called()


def test_delete_removes_key_and_both_indexes():
    persistency, client = _persistency()
    client.get.return_value = _state().to_dict()
    persistency.delete("t-1")
    client.delete.assert_called_once_with("jobstate:t-1")
    client.zset_remove.assert_any_call(JOB_STATE_INDEX_PENDING, "t-1")
    client.zset_remove.assert_any_call("jobstate:index:user:alice", "t-1")


def test_save_recurring_job_populates_schedule_index():
    persistency, client = _persistency()
    state = _state()
    state.schedule_name = "imip.scan_inbox"
    persistency.save(state)
    assert any(
        call.args[0] == "jobstate:index:schedule:imip.scan_inbox"
        for call in client.zset_add.call_args_list
    )


def test_list_by_schedule_uses_schedule_index():
    persistency, client = _persistency()
    client.zset_revrange.return_value = ["t-recent", "t-old"]
    state_recent = _state("t-recent")
    state_recent.schedule_name = "imip.scan_inbox"
    state_old = _state("t-old")
    state_old.schedule_name = "imip.scan_inbox"
    client.get.side_effect = [state_recent.to_dict(), state_old.to_dict()]
    result = persistency.list_by_schedule("imip.scan_inbox", limit=10)
    client.zset_revrange.assert_called_once_with("jobstate:index:schedule:imip.scan_inbox", 0, 9)
    assert [s.job_id for s in result] == ["t-recent", "t-old"]


def test_save_system_job_skips_user_index():
    """A job with user_uid=None (system job) must not write to any user index."""
    persistency, client = _persistency()
    state = _state(user=None)
    persistency.save(state)
    user_index_calls = [c for c in client.zset_add.call_args_list if c.args[0].startswith("jobstate:index:user:")]
    assert user_index_calls == []
    # The pending index is still maintained.
    assert any(c.args[0] == JOB_STATE_INDEX_PENDING for c in client.zset_add.call_args_list)


def test_delete_recurring_job_cleans_schedule_index():
    persistency, client = _persistency()
    state = _state()
    state.schedule_name = "imip.scan_inbox"
    client.get.return_value = state.to_dict()
    persistency.delete("t-1")
    client.zset_remove.assert_any_call("jobstate:index:schedule:imip.scan_inbox", "t-1")
