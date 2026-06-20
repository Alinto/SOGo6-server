"""Worker-side Agent job running a user-triggered sync of one external ICS calendar.

Fetches the remote .ics and mirrors it into the local calendar through the shared SyncEngine
(which also updates the calendar's sync_status / last_sync). The result carries the sync counters
(small), returned inline in ``JobState.result``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agent.jobs.Job import Job, agent_job
from app.config.settings.ProcessSetting import process_config
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar
from app.module.calendar.jobs.JobRequestSyncExternalManual import JobRequestSyncExternalManual

if TYPE_CHECKING:
    from app.module.calendar.model.CalSyncResult import CalSyncResult


@agent_job
class JobSyncExternalManual(Job):
    """Worker-side counterpart of :class:`JobRequestSyncExternalManual`."""

    request_class = JobRequestSyncExternalManual

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Sync the requested external calendar and return the sync counters.

        :param payload: dict produced by ``JobRequestSyncExternalManual.payload``.
        :param user_uid: identity of the calendar owner; ``None`` is rejected.
        :param job_id: Celery-provided id of the running job. Unused here.
        :return: ``{"inserted": int, "updated": int, "deleted": int, "total": int, "skipped": int}``.
        :raises ValueError: ``user_uid`` is ``None``.
        """
        if user_uid is None:
            raise ValueError("JobSyncExternalManual requires a user_uid")
        inter: InterfaceAgentCalendar = InterfaceAgentCalendar(process_config, user_uid)
        result: CalSyncResult = inter.sync_external_calendar(payload["calendar_key"])
        return result.to_dict()
