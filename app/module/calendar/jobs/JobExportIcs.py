"""Worker-side Agent job exporting a calendar as a VCALENDAR result.

The serialised ICS is offloaded to ``JobLargeStore`` because it can be
sizeable (thousands of events). ``JobState.result`` only carries the storage
reference plus light metadata. The companion request DTO lives in
``JobRequestExportIcs`` (separate file to keep the enqueue side cycle-free).
"""
from __future__ import annotations

from typing import Any

from app.agent.Agent import agent
from app.agent.jobs.Job import Job, agent_job
from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef
from app.config.settings.ProcessSetting import process_config
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar
from app.module.calendar.jobs.JobRequestExportIcs import JobRequestExportIcs
from app.utils.datetime.DateTimeUtils import parse_iso


@agent_job
class JobExportIcs(Job):
    """Worker-side counterpart of :class:`JobRequestExportIcs`."""

    request_class = JobRequestExportIcs

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Serialise the requested calendar and store the result blob.

        :param payload: dict produced by ``JobRequestExportIcs.payload`` and rehydrated
            here through ``JobRequestExportIcs(**payload)``.
        :type payload: dict[str, Any]
        :param user_uid: identity of the calendar owner; ``None`` is rejected because
            an export is always scoped to a user.
        :type user_uid: str | None
        :param job_id: Celery-provided id of the running job. Unused here but kept
            by contract for future per-job tracing.
        :type job_id: str
        :return: ``{"large_result": <ref dict>, "filename": "<key>.ics", "size_bytes": int}``
            where ``large_result`` is the reference dict produced by the configured
            ``JobLargeStore`` backend.
        :rtype: dict[str, Any]
        :raises ValueError: ``user_uid`` is ``None``.
        """
        if user_uid is None:
            raise ValueError("JobExportIcs requires a user_uid")
        req: JobRequestExportIcs = JobRequestExportIcs(**payload)
        inter: InterfaceAgentCalendar = InterfaceAgentCalendar(process_config, user_uid)
        ics: str = inter.export_calendar(
            req.calendar_key,
            date_start=parse_iso(req.date_start),
            date_end=parse_iso(req.date_end),
        )
        encoded: bytes = ics.encode("utf-8")
        ref: JobLargeRef = agent.get_large_store().save(encoded, "text/calendar")
        return {
            "large_result": ref.to_dict(),
            "filename": f"{req.calendar_key}.ics",
            "size_bytes": len(encoded),
        }
