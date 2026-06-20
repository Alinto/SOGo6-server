"""Periodic job auto-syncing external ICS calendars whose interval has elapsed (triggered by Celery Beat).

System-wide sweep (no user scope): every 5 minutes it picks the external calendars that are due
(``now - last_sync >= sync_interval_minutes``) and syncs each inline through the shared SyncEngine,
one failure never aborting the batch. The request DTO and the worker live in the same file: this job
is enqueued only by the beat schedule, so there is no enqueue-side module dependency that would force
a cycle-breaking split (same shape as the large-store cleanup job).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.Job import Job, agent_job
from app.agent.jobs.JobRequest import JobRequest
from app.config.settings.ProcessSetting import process_config
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar


@dataclass
class JobRequestSyncExternalAuto(JobRequest):
    """Inputs for the periodic external-calendar auto-sync (none - it sweeps all due calendars)."""

    name: ClassVar[str] = "calendar.sync.external.auto"
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False
    cron: ClassVar[str] = "*/5 * * * *"  # Every 5 minutes

    def payload(self) -> dict[str, Any]:
        """No input: the sweep reads each calendar's interval from its sync_config."""
        return {}


@agent_job
class JobSyncExternalAuto(Job):
    """Worker-side counterpart of :class:`JobRequestSyncExternalAuto`."""

    request_class = JobRequestSyncExternalAuto

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Sync every external calendar that is due and return the aggregate counts.

        :param payload: unused (empty).
        :param user_uid: ``None`` - this is a system job with no owner.
        :param job_id: Celery-provided id of the running job. Unused here.
        :return: ``{"total": int, "synced": int, "failed": int, "skipped": int}``.
        """
        interface: InterfaceAgentCalendar = InterfaceAgentCalendar(process_config, user_uid)
        return interface.sync_all_due_external()
