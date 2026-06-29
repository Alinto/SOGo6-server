"""Periodic job emailing event reminders whose trigger time has just elapsed (triggered by Celery Beat).

System-wide sweep (no user scope): every minute it picks the email reminders that became due since the
last run and sends each to its owner inline through the outgoing mail module, one failure never aborting
the batch. A Redis watermark gives the dedup window so a reminder fires exactly once. The request DTO and
the worker live in the same file: this job is enqueued only by the beat schedule, so there is no
enqueue-side module dependency that would force a cycle-breaking split (same shape as the auto-sync job).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.Job import Job, agent_job
from app.agent.jobs.JobRequest import JobRequest
from app.config.settings.ProcessSetting import process_config
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar


@dataclass
class JobRequestSendEmailReminders(JobRequest):
    """Inputs for the periodic email-reminder sweep (none - it scans every due reminder)."""

    name: ClassVar[str] = "calendar.reminder.email"
    soft_timeout_seconds: ClassVar[int] = 50
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False
    cron: ClassVar[str] = "* * * * *"  # Every minute

    def payload(self) -> dict[str, Any]:
        """No input: the sweep reads the due reminders and the dedup watermark itself."""
        return {}


@agent_job
class JobSendEmailReminders(Job):
    """Worker-side counterpart of :class:`JobRequestSendEmailReminders`."""

    request_class = JobRequestSendEmailReminders

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Email every reminder due since the last run and return the aggregate counts.

        :param payload: unused (empty).
        :param user_uid: ``None`` - this is a system job with no owner.
        :param job_id: Celery-provided id of the running job. Unused here.
        :return: ``{"total": int, "sent": int, "failed": int}``.
        """
        interface: InterfaceAgentCalendar = InterfaceAgentCalendar(process_config, user_uid)
        return interface.send_due_email_reminders()
