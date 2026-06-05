"""Resume-or-fail policy applied to orphan jobs at worker startup (and later by Beat)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.agent.AgentConst import JOB_RECOVERY_LOCK_KEY, JOB_RECOVERY_LOCK_TTL_SECONDS
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus
from app.utils.logger.logger import logger_agent

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.jobs.JobPersistency import JobPersistency
    from app.manager.cache.ClientRedis import ClientRedis


class JobRecovery:
    """Applies the resume / FAILURE policy on orphan jobs.

    Each Job subclass declares whether it can be safely re-run after an interruption
    (``resume=True``). At boot, every non-terminal JobState left by the previous run is
    inspected: eligible ones are requeued with the same ``job_id``, others are marked
    FAILURE with a clear error.

    A Redis lock prevents multiple agent workers from sweeping at the same time.
    """

    def __init__(
        self, agent: Agent, persistency: JobPersistency, cache: ClientRedis,
    ) -> None:
        self._agent: Agent = agent
        self._persistency: JobPersistency = persistency
        self._cache: ClientRedis = cache

    def reconcile_orphans(self) -> tuple[int, int]:
        """Sweep non-terminal JobStates left over by the previous run.

        For each orphan the policy is: requeue with the same ``job_id`` when
        the matching Job declares ``resume=True`` **and** ``attempts < max_try``,
        mark FAILURE otherwise. Jobs unknown to the current process (e.g.
        removed from the code base) are also marked FAILURE.

        Acquires a short-lived Redis lock so concurrent agent workers cooperate:
        only the lock holder runs the sweep; others see ``(0, 0)``.

        :return: ``(resumed_count, failed_count)``; ``(0, 0)`` when another
            worker holds the lock or there are no orphans.
        :rtype: tuple[int, int]
        """
        if not self._cache.set(
            JOB_RECOVERY_LOCK_KEY, "1", ttl=JOB_RECOVERY_LOCK_TTL_SECONDS, nx=True,
        ):
            logger_agent.debug("JobRecovery: another worker holds the lock, skipping")
            return 0, 0
        logger_agent.info("JobRecovery: scanning pending jobs")
        resumed: int = 0
        failed: int = 0
        for state in self._persistency.list_pending(limit=10_000):
            if state.status not in (JobStatus.STARTED, JobStatus.PENDING):
                continue
            registered = self._agent.get_job_handler(state.name)
            resume: bool = registered.request_class.resume if registered is not None else False
            eligible: bool = (
                registered is not None
                and resume
                and state.attempts < state.max_try
            )
            if eligible:
                state.status = JobStatus.PENDING
                state.date_start = None
                state.date_end = None
                state.duration_seconds = None
                self._persistency.save(state)
                self._agent.create_job(
                    state.name, state.payload, user_uid=state.user_uid, job_id=state.job_id,
                )
                logger_agent.info(
                    "JobRecovery: resumed job_id=%s name=%s attempts=%d/%d",
                    state.job_id, state.name, state.attempts, state.max_try,
                )
                resumed += 1
            else:
                state.status = JobStatus.FAILURE
                state.error = (
                    "Job interrupted at startup and not eligible for resume "
                    f"(resume={resume if registered else 'unknown'}, "
                    f"attempts={state.attempts}/{state.max_try})"
                )
                state.date_end = datetime.now(timezone.utc)
                if state.date_start:
                    state.duration_seconds = (state.date_end - state.date_start).total_seconds()
                self._persistency.save(state)
                # Lifecycle hooks won't fire for an orphan we mark FAILURE manually —
                # release the concurrency lock ourselves so the user can re-enqueue.
                self._cache.delete(JobState.concurrency_lock_key(state.name, state.user_uid))
                logger_agent.warning(
                    "JobRecovery: marked FAILURE job_id=%s name=%s reason=%s",
                    state.job_id, state.name, state.error,
                )
                failed += 1
        logger_agent.info("JobRecovery: done resumed=%d failed=%d", resumed, failed)
        return resumed, failed
