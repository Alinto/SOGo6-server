"""Unit tests for the Job abstract class and Agent.register."""
from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.Agent import agent
from app.agent.jobs.Job import Job
from app.agent.jobs.JobRequest import JobRequest


@dataclass
class _ExampleRequest(JobRequest):
    name: ClassVar[str] = "test.example"
    soft_timeout_seconds: ClassVar[int] = 5

    def payload(self) -> dict[str, Any]:
        return {}


class _ExampleTask(Job):
    request_class = _ExampleRequest

    def process(self, payload, *, user_uid, job_id):
        return {"echo": payload, "user_uid": user_uid, "job_id": job_id}


def test_process_returns_a_dict_with_context():
    out = _ExampleTask()._run("task-42", {"k": "v"}, "alice")
    assert out == {"echo": {"k": "v"}, "user_uid": "alice", "job_id": "task-42"}


def test_process_accepts_none_user_uid_for_system_tasks():
    out = _ExampleTask()._run("task-99", {"job": "purge"}, None)
    assert out["user_uid"] is None


def test_register_then_get_job_handler():
    handler = _ExampleTask()
    agent.register_job_handler(handler)
    assert agent.get_job_handler("test.example") is handler
    assert agent.get_job_handler("unknown") is None
