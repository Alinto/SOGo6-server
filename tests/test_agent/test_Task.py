"""Unit tests for the Task base class and AgentApp.register."""
from typing import Any
from unittest.mock import MagicMock

from app.agent.AgentApp import agent
from app.agent.tasks.Task import Task


class _Noop(Task):
    name = "test.noop"
    soft_timeout_seconds = 5
    max_retry = 0

    def process(self, payload, *, user_uid, task_id):
        return {"echo": payload, "user_uid": user_uid, "task_id": task_id}


def test_process_returns_a_dict_with_context():
    t = _Noop()
    out = t._run("task-42", {"k": "v"}, "alice")
    assert out == {"echo": {"k": "v"}, "user_uid": "alice", "task_id": "task-42"}


def test_process_accepts_none_user_uid_for_system_tasks():
    t = _Noop()
    out = t._run("task-99", {"job": "purge"}, None)
    assert out["user_uid"] is None


def test_register_adds_task_to_underlying_app():
    t = _Noop()
    agent.register(t)
    # Celery exposes registered tasks by name in its internal registry.
    assert "test.noop" in agent.for_celery_cli.tasks
    registered = agent.for_celery_cli.tasks["test.noop"]
    # Soft / hard limits derived from the Task subclass attributes.
    assert registered.soft_time_limit == 5
    assert registered.time_limit == 15
