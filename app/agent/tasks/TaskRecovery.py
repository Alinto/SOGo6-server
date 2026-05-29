"""Resume-or-fail policy applied to orphan tasks at worker startup (and later by Beat)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.agent.AgentConst import TASK_RECOVERY_LOCK_KEY, TASK_RECOVERY_LOCK_TTL_SECONDS
from app.agent.tasks.TaskStatus import TaskStatus
from app.utils.logger.logger import logger

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.tasks.TaskPersistency import TaskPersistency
    from app.manager.cache.ClientRedis import ClientRedis


class TaskRecovery:
    """Applies the resume / FAILURE policy on orphan tasks.

    Each Task subclass declares whether it can be safely re-run after an interruption
    (``resume=True``). At boot, every non-terminal TaskState left by the previous run is
    inspected: eligible ones are requeued with the same ``task_id``, others are marked
    FAILURE with a clear error.

    A Redis lock prevents multiple agent workers from sweeping at the same time.
    """

    def __init__(
        self, agent: Agent, persistency: TaskPersistency, cache: ClientRedis,
    ) -> None:
        self._agent: Agent = agent
        self._persistency: TaskPersistency = persistency
        self._cache: ClientRedis = cache

    def reconcile_orphans(self) -> tuple[int, int]:
        """Return ``(resumed_count, failed_count)``. Returns ``(0, 0)`` when another
        worker holds the lock."""
        if not self._cache.set(
            TASK_RECOVERY_LOCK_KEY, "1", ttl=TASK_RECOVERY_LOCK_TTL_SECONDS, nx=True,
        ):
            return 0, 0
        resumed: int = 0
        failed: int = 0
        for state in self._persistency.list_pending(limit=10_000):
            if state.status not in (TaskStatus.STARTED, TaskStatus.PENDING):
                continue
            registered = self._agent.get_task(state.name)
            eligible: bool = (
                registered is not None
                and registered.resume
                and state.attempts < state.max_try
            )
            if eligible:
                state.status = TaskStatus.PENDING
                state.date_start = None
                state.date_end = None
                state.duration_seconds = None
                self._persistency.save(state)
                self._agent.create_task(
                    state.name, state.payload, user_uid=state.user_uid, task_id=state.task_id,
                )
                resumed += 1
            else:
                state.status = TaskStatus.FAILURE
                state.error = (
                    "Task interrupted at startup and not eligible for resume "
                    f"(resume={registered.resume if registered else 'unknown'}, "
                    f"attempts={state.attempts}/{state.max_try})"
                )
                state.date_end = datetime.now(timezone.utc)
                if state.date_start:
                    state.duration_seconds = (state.date_end - state.date_start).total_seconds()
                self._persistency.save(state)
                failed += 1
        if resumed or failed:
            logger.info("TaskRecovery: resumed=%d, failed=%d", resumed, failed)
        return resumed, failed
