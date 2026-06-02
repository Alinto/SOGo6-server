"""Two-phase cancellation: SIGTERM, grace wait, SIGKILL. Idempotent."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.agent.tasks.TaskStatus import TaskStatus
from app.utils.logger.logger import logger_agent

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.tasks.TaskPersistency import TaskPersistency


class TaskCanceller:
    """Cooperative-then-forced task cancellation.

    Sends ``SIGTERM`` to the running task so it can clean up (close files,
    release locks). Polls the TaskState; if the task hasn't reached a terminal
    status within the grace window, escalates to ``SIGKILL``.
    """

    _POLL_INTERVAL_SECONDS: float = 0.1

    def __init__(self, agent: Agent, persistency: TaskPersistency) -> None:
        self._agent: Agent = agent
        self._persistency: TaskPersistency = persistency

    def cancel(self, task_id: str, *, soft_wait_seconds: float = 5.0) -> None:
        """Cancel a running task, escalating SIGTERM → SIGKILL if needed.

        No-op when the task is unknown (already TTL-expired or never published)
        or already in a terminal state. Safe to call multiple times.

        :param task_id: id of the task to cancel.
        :type task_id: str
        :param soft_wait_seconds: grace period after ``SIGTERM`` before escalating
            to ``SIGKILL``. Should comfortably exceed the time a well-behaved task
            takes to clean up.
        :type soft_wait_seconds: float
        """
        state = self._persistency.get(task_id)
        if state is None:
            logger_agent.debug("TaskCanceller: unknown task_id=%s, no-op", task_id)
            return
        if TaskStatus.is_terminal(state.status):
            logger_agent.debug(
                "TaskCanceller: task_id=%s already %s, no-op", task_id, state.status.value,
            )
            return
        logger_agent.info("TaskCanceller: SIGTERM task_id=%s grace=%.1fs", task_id, soft_wait_seconds)
        self._agent.cancel(task_id, signal="SIGTERM")
        # TODO: this blocks the caller thread for up to ``soft_wait_seconds``. Acceptable
        # for admin API calls today; if it ever becomes hot, move the SIGKILL escalation
        # to a system task (client_agent.start("admin.kill_if_alive", ...)).
        deadline: float = time.monotonic() + soft_wait_seconds
        while time.monotonic() < deadline:
            current = self._persistency.get(task_id)
            if current is None or TaskStatus.is_terminal(current.status):
                return
            time.sleep(self._POLL_INTERVAL_SECONDS)
        logger_agent.warning("TaskCanceller: SIGKILL task_id=%s (grace expired)", task_id)
        self._agent.cancel(task_id, signal="SIGKILL")
