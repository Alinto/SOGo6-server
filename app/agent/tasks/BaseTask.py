from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.tasks.TaskRequest import TaskRequest


class AgentTaskCancelled(InterruptedError):
    """Raised inside a Task to signal cooperative cancellation."""


class BaseTask(ABC):
    """Base class for every Agent task. Subclasses set ``request_class`` to their
    companion ``TaskRequest`` and implement :meth:`process`. The Request is the
    single source of truth for the task name and execution metadata (max_try,
    soft_timeout_seconds, resume) — the Task reads everything through it.
    """

    request_class: ClassVar[type[TaskRequest]]

    @abstractmethod
    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, task_id: str,
    ) -> dict[str, Any]:
        """Run the task and return a JSON-serialisable result."""

    def _run(self, task_id: str, payload: dict[str, Any], user_uid: str | None) -> dict[str, Any]:
        return self.process(payload, user_uid=user_uid, task_id=task_id)
