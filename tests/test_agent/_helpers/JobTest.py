"""Test-only validation task and its companion Request. Lives under ``tests/``
so it never ships in production."""
from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.agent.jobs.Job import Job
from app.agent.jobs.JobRequest import JobRequest


@dataclass
class TaskTestRequest(JobRequest):
    """Companion Request for TaskTest. Drives the three payload-driven modes."""

    name: ClassVar[str] = "system.test"
    max_try: ClassVar[int] = 1
    soft_timeout_seconds: ClassVar[int] = 60
    resume: ClassVar[bool] = False

    seconds: float | None = None
    raise_error: bool = False
    crash: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        out: dict[str, Any] = dict(self.extras)
        if self.seconds is not None:
            out["seconds"] = self.seconds
        if self.raise_error:
            out["raise"] = True
        if self.crash:
            out["crash"] = True
        return out


class TaskTest(Job):
    """No-op task with payload-driven modes for testing every lifecycle path."""

    request_class = TaskTestRequest

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        seconds: float = float(payload.get("seconds", 0))
        if seconds > 0:
            time.sleep(seconds)
        if payload.get("raise"):
            raise RuntimeError("TaskTest forced failure (payload.raise=True)")
        if payload.get("crash"):
            # Dereferences NULL → segfault. Kills the worker process; only used to
            # exercise the orphan-task path in integration tests.
            ctypes.string_at(0)
        return {"echo": payload, "user_uid": user_uid, "job_id": job_id}
