"""Two-phase cancellation: SIGTERM, grace wait, SIGKILL. Idempotent."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.agent.tasks.TaskStatus import TaskStatus

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.tasks.TaskPersistency import TaskPersistency


class TaskCanceller:
    """SIGTERM → poll until terminal or timeout → SIGKILL."""

    _POLL_INTERVAL_SECONDS: float = 0.1

    def __init__(self, agent: Agent, persistency: TaskPersistency) -> None:
        self._agent: Agent = agent
        self._persistency: TaskPersistency = persistency

    def cancel(self, task_id: str, *, soft_wait_seconds: float = 5.0) -> None:
        """Cancel a running task. No-op if unknown or already terminal."""
        state = self._persistency.get(task_id)
        if state is None or TaskStatus.is_terminal(state.status):
            return
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
        self._agent.cancel(task_id, signal="SIGKILL")
