"""Base class for every SOGo Agent task.

A Task is a small unit of work with a name, a soft timeout, a max retry count, and a
``process`` method that does the actual work. Subclasses must inherit from :class:`Task`
and implement :meth:`process`. Registration with the underlying task framework is delegated
to :meth:`AgentApp.register`, which is the only place the framework-specific decorator
lives — Task itself knows nothing about Celery.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Task(ABC):
    """Abstract Agent task.

    Subclass contract:
        - ``name``: unique routing key (e.g. ``"imip.send"``). Required.
        - ``soft_timeout_seconds``: after this delay the task receives a cooperative cancel
          signal and can clean up before the hard kill (soft + 10s).
        - ``max_retry``: number of retries before the task is marked FAILURE for good.
        - ``process``: the actual work.

    Subclasses are expected to be idempotent — workers can crash and a task may be
    redelivered (``task_acks_late=True``).
    """
    name: str = ""
    soft_timeout_seconds: int = 300
    max_retry: int = 0

    @abstractmethod
    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, task_id: str,
    ) -> dict[str, Any]:
        """Execute the task and return a JSON-serialisable result.

        :param payload: caller-supplied parameters (already deserialised from JSON).
        :param user_uid: the user this task runs on behalf of, or ``None`` for
            system/admin tasks (e.g. periodic purge) that are not tied to a user.
        :param task_id: the id assigned by the framework — useful for logging and to look
            up the current TaskState if needed.
        """

    def _run(self, task_id: str, payload: dict[str, Any], user_uid: str | None) -> dict[str, Any]:
        """Internal entrypoint called by the framework wrapper. Keeps :meth:`process` clean."""
        return self.process(payload, user_uid=user_uid, task_id=task_id)
