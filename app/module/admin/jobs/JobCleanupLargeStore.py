"""Periodic job purging stale large-store blobs (triggered by Celery Beat).

Targets the FILE backend, whose blobs do not expire on their own (the in-memory
backend relies on the Redis TTL). The request DTO and the worker live in the same
file: this job is enqueued only by the beat schedule, so there is no enqueue-side
module dependency that would force a cycle-breaking split.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.Agent import agent
from app.agent.jobs.Job import Job, agent_job
from app.agent.jobs.JobRequest import JobRequest
from app.config.settings.ProcessSetting import process_config


@dataclass
class JobRequestCleanupLargeStore(JobRequest):
    """Inputs for the large-store cleanup job (none - the age comes from config)."""

    name: ClassVar[str] = "admin.cleanup.large_store"
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False
    cron: ClassVar[str] = "0 * * * *"  # Every hour

    def payload(self) -> dict[str, Any]:
        """No input: the cleanup reads its threshold from the process settings."""
        return {}


@agent_job
class JobCleanupLargeStore(Job):
    """Worker-side counterpart of :class:`JobRequestCleanupLargeStore`."""

    request_class = JobRequestCleanupLargeStore

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Purge blobs older than ``SOGO_P_AGENT_LARGE_STORE_MAX_AGE_SECONDS``.

        :param payload: unused (empty).
        :type payload: dict[str, Any]
        :param user_uid: ``None`` - this is a system job with no owner.
        :type user_uid: str | None
        :param job_id: Celery-provided id of the running job. Unused here.
        :type job_id: str
        :return: ``{"removed": int}`` - how many blobs were deleted.
        :rtype: dict[str, Any]
        """
        max_age: int = process_config.SOGO_P_AGENT_LARGE_STORE_MAX_AGE_SECONDS
        removed: int = agent.get_large_store().purge(max_age)
        return {"removed": removed}
