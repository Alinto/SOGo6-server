"""Two-phase cancellation: SIGTERM, grace wait, SIGKILL. Idempotent."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.agent.jobs.JobStatus import JobStatus
from app.utils.logger.logger import logger_agent

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.jobs.JobPersistency import JobPersistency
    from app.agent.jobs.JobState import JobState


class JobCanceller:
    """Cooperative-then-forced job cancellation.

    Sends ``SIGTERM`` to the running job so it can clean up (close files,
    release locks). Polls the JobState; if the job hasn't reached a terminal
    status within the grace window, escalates to ``SIGKILL``.
    """

    _POLL_INTERVAL_SECONDS: float = 0.1

    def __init__(self, agent: Agent, persistency: JobPersistency) -> None:
        self._agent: Agent = agent
        self._persistency: JobPersistency = persistency

    def cancel(self, job_id: str, *, soft_wait_seconds: float = 5.0) -> None:
        """Cancel a running job, escalating SIGTERM -> SIGKILL if needed.

        No-op when the job is unknown (already TTL-expired or never published)
        or already in a terminal state. Safe to call multiple times.

        :param job_id: id of the job to cancel.
        :type job_id: str
        :param soft_wait_seconds: grace period after ``SIGTERM`` before escalating
            to ``SIGKILL``. Should comfortably exceed the time a well-behaved job
            takes to clean up.
        :type soft_wait_seconds: float
        """
        state: JobState | None = self._persistency.get(job_id)
        if state is None:
            logger_agent.debug("JobCanceller: unknown job_id=%s, no-op", job_id)
            return
        if JobStatus.is_terminal(state.status):
            logger_agent.debug(
                "JobCanceller: job_id=%s already %s, no-op", job_id, state.status.value,
            )
            return
        logger_agent.info("JobCanceller: SIGTERM job_id=%s grace=%.1fs", job_id, soft_wait_seconds)
        self._agent.cancel(job_id, signal="SIGTERM")
        # TODO: this blocks the caller thread for up to ``soft_wait_seconds``. Acceptable
        # for admin API calls today; if it ever becomes hot, move the SIGKILL escalation
        # to a system job (client_agent.start("admin.kill_if_alive", ...)).
        deadline: float = time.monotonic() + soft_wait_seconds
        while time.monotonic() < deadline:
            current: JobState | None = self._persistency.get(job_id)
            if current is None or JobStatus.is_terminal(current.status):
                return
            time.sleep(self._POLL_INTERVAL_SECONDS)
        logger_agent.warning("JobCanceller: SIGKILL job_id=%s (grace expired)", job_id)
        self._agent.cancel(job_id, signal="SIGKILL")
