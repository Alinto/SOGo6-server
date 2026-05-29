"""Unit tests for the BaseTask abstract class and Agent.register."""
from app.agent.Agent import agent
from app.agent.tasks.BaseTask import BaseTask


class _ExampleTask(BaseTask):
    name = "test.example"
    soft_timeout_seconds = 5

    def process(self, payload, *, user_uid, task_id):
        return {"echo": payload, "user_uid": user_uid, "task_id": task_id}


def test_process_returns_a_dict_with_context():
    out = _ExampleTask()._run("task-42", {"k": "v"}, "alice")
    assert out == {"echo": {"k": "v"}, "user_uid": "alice", "task_id": "task-42"}


def test_process_accepts_none_user_uid_for_system_tasks():
    out = _ExampleTask()._run("task-99", {"job": "purge"}, None)
    assert out["user_uid"] is None


def test_register_then_get_task():
    task = _ExampleTask()
    agent.register(task)
    assert agent.get_task("test.example") is task
    assert agent.get_task("unknown") is None
