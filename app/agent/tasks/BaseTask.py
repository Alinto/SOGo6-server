from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentTaskCancelled(InterruptedError):
    """Raised inside a Task to signal cooperative cancellation."""

class BaseTask(ABC):
    """Base class for every Agent task. Subclasses set the four class attributes and
    implement :meth:`process`.

    ``resume=True`` requeues an interrupted task at startup as long as ``attempts < max_try``.
    Set ``False`` for tasks with non-idempotent side effects (sending email, third-party API).
    """
    name: str = ""
    soft_timeout_seconds: int = 300
    max_try: int = 1
    resume: bool = True

    @abstractmethod
    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, task_id: str,
    ) -> dict[str, Any]:
        """Run the task and return a JSON-serialisable result."""

    def _run(self, task_id: str, payload: dict[str, Any], user_uid: str | None) -> dict[str, Any]:
        return self.process(payload, user_uid=user_uid, task_id=task_id)
