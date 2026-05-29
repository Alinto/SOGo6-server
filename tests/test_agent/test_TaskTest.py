"""In-process tests for TaskTest. End-to-end behaviour (crash, timeout) is covered
by integration tests against a real worker."""
import time
from unittest.mock import patch

import pytest

from tests.test_agent._helpers.TaskTest import TaskTest
from app.agent.tasks.BaseTask import AgentTaskCancelled


def test_returns_payload_echo():
    out = TaskTest().process({"k": "v"}, user_uid="alice", task_id="t-1")
    assert out["echo"] == {"k": "v"}
    assert out["user_uid"] == "alice"
    assert out["task_id"] == "t-1"


def test_raises_when_payload_asks_for_failure():
    with pytest.raises(RuntimeError, match="forced failure"):
        TaskTest().process({"raise": True}, user_uid=None, task_id="t-2")


def test_sleeps_for_the_requested_duration():
    start = time.monotonic()
    TaskTest().process({"seconds": 0.05}, user_uid=None, task_id="t-3")
    assert time.monotonic() - start >= 0.05


def test_crash_dereferences_a_null_pointer():
    """A real crash would kill pytest; we mock ctypes to verify the intent."""
    with patch("tests.test_agent._helpers.TaskTest.ctypes.string_at") as ctypes_call:
        TaskTest().process({"crash": True}, user_uid=None, task_id="t-4")
    ctypes_call.assert_called_once_with(0)


def test_cooperative_cancel_is_signalled_via_exception():
    """When the cancellation signal arrives mid-process, the Task code propagates
    AgentTaskCancelled (raised by the SIGTERM handler installed at runtime). Here we
    simulate the propagation by patching ``time.sleep`` to raise."""
    with patch("tests.test_agent._helpers.TaskTest.time.sleep", side_effect=AgentTaskCancelled):
        with pytest.raises(AgentTaskCancelled):
            TaskTest().process({"seconds": 60}, user_uid=None, task_id="t-5")


def test_soft_timeout_propagates_to_the_caller():
    """Celery raises SoftTimeLimitExceeded inside the worker thread on timeout. The Task
    code does not catch it — it propagates and lifecycle hooks observe FAILURE. We model
    that path here by injecting the exception through ``time.sleep``."""
    class _Soft(Exception):
        pass
    with patch("tests.test_agent._helpers.TaskTest.time.sleep", side_effect=_Soft):
        with pytest.raises(_Soft):
            TaskTest().process({"seconds": 60}, user_uid=None, task_id="t-6")


def test_attributes_for_resume_policy():
    task = TaskTest()
    assert task.name == "system.test"
    assert task.resume is False
    assert task.max_try == 1
