"""Resume-or-fail policy applied to orphan tasks at worker startup (and later by Beat)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.agent.AgentConst import TASK_RECOVERY_LOCK_KEY, TASK_RECOVERY_LOCK_TTL_SECONDS
from app.agent.tasks.TaskStatus import TaskStatus
from app.utils.logger.logger import logger_agent

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
        """Sweep non-terminal TaskStates left over by the previous run.

        For each orphan the policy is: requeue with the same ``task_id`` when
        the matching Task declares ``resume=True`` **and** ``attempts < max_try``,
        mark FAILURE otherwise. Tasks unknown to the current process (e.g.
        removed from the code base) are also marked FAILURE.

        Acquires a short-lived Redis lock so concurrent agent workers cooperate:
        only the lock holder runs the sweep; others see ``(0, 0)``.

        :return: ``(resumed_count, failed_count)``; ``(0, 0)`` when another
            worker holds the lock or there are no orphans.
        :rtype: tuple[int, int]
        """
        if not self._cache.set(
            TASK_RECOVERY_LOCK_KEY, "1", ttl=TASK_RECOVERY_LOCK_TTL_SECONDS, nx=True,
        ):
            logger_agent.debug("TaskRecovery: another worker holds the lock, skipping")
            return 0, 0
        logger_agent.info("TaskRecovery: scanning pending tasks")
        resumed: int = 0
        failed: int = 0
        for state in self._persistency.list_pending(limit=10_000):
            if state.status not in (TaskStatus.STARTED, TaskStatus.PENDING):
                continue
            registered = self._agent.get_task_handler(state.name)
            resume: bool = registered.request_class.resume if registered is not None else False
            eligible: bool = (
                registered is not None
                and resume
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
                logger_agent.info(
                    "TaskRecovery: resumed task_id=%s name=%s attempts=%d/%d",
                    state.task_id, state.name, state.attempts, state.max_try,
                )
                resumed += 1
            else:
                state.status = TaskStatus.FAILURE
                state.error = (
                    "Task interrupted at startup and not eligible for resume "
                    f"(resume={resume if registered else 'unknown'}, "
                    f"attempts={state.attempts}/{state.max_try})"
                )
                state.date_end = datetime.now(timezone.utc)
                if state.date_start:
                    state.duration_seconds = (state.date_end - state.date_start).total_seconds()
                self._persistency.save(state)
                logger_agent.warning(
                    "TaskRecovery: marked FAILURE task_id=%s name=%s reason=%s",
                    state.task_id, state.name, state.error,
                )
                failed += 1
        logger_agent.info("TaskRecovery: done resumed=%d failed=%d", resumed, failed)
        return resumed, failed
