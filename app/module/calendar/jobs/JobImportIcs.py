"""Worker-side Agent job importing an uploaded .ics file into a calendar.

The uploaded file is read back from the agent blob store (saved by the API before
enqueue), applied to the calendar, then deleted - an input blob has no reason to
outlive its consumption. The result carries the import counters (small), returned
inline in ``JobState.result``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agent.Agent import agent
from app.agent.jobs.Job import Job, agent_job
from app.config.settings.ProcessSetting import process_config
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar
from app.module.calendar.jobs.JobRequestImportIcs import JobRequestImportIcs

if TYPE_CHECKING:
    from app.manager.storage.ClientStorage import ClientStorage
    from app.module.calendar.model.CalSyncResult import CalSyncResult


@agent_job
class JobImportIcs(Job):
    """Worker-side counterpart of :class:`JobRequestImportIcs`."""

    request_class = JobRequestImportIcs

    def public_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Hide ``source_ref`` from the owner view: it is an internal blob pointer
        (a storage locator, e.g. a file path) of no use to the client.

        :param payload: the raw payload stored in ``JobState.payload``.
        :type payload: dict[str, Any]
        :return: a copy of the payload without ``source_ref``.
        :rtype: dict[str, Any]
        """
        return {key: value for key, value in payload.items() if key != "source_ref"}

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Apply the uploaded ICS to the calendar and return the import counters.

        :param payload: dict produced by ``JobRequestImportIcs.payload``.
        :type payload: dict[str, Any]
        :param user_uid: identity of the calendar owner; ``None`` is rejected.
        :type user_uid: str | None
        :param job_id: Celery-provided id of the running job. Unused here.
        :type job_id: str
        :return: ``{"inserted": int, "updated": int, "deleted": int, "total": int, "skipped": int}``.
        :rtype: dict[str, Any]
        :raises ValueError: ``user_uid`` is ``None`` or the request carries no ``source_ref``.
        """
        source_ref: str | None = payload.get("source_ref")
        if not source_ref:
            raise ValueError("JobImportIcs requires a source_ref")
        store: ClientStorage = agent.get_large_store()
        try:
            # An input blob is single-use: once we hold its ref, any failure below
            # (including a missing user_uid) must still drop it - hence inside the try.
            if user_uid is None:
                raise ValueError("JobImportIcs requires a user_uid")
            calendar_key: str = payload["calendar_key"]
            loaded: tuple[bytes, str] | None = store.load(source_ref)
            if loaded is None:
                raise FileNotFoundError(f"Import blob missing or expired: {source_ref!r}")
            content: bytes = loaded[0]
            try:
                ics_text: str = content.decode("utf-8")
            except UnicodeDecodeError:
                ics_text = content.decode("latin-1")
            inter: InterfaceAgentCalendar = InterfaceAgentCalendar(process_config, user_uid)
            result: CalSyncResult = inter.import_calendar(calendar_key, ics_text)
            return {
                "inserted": result.inserted,
                "updated": result.updated,
                "deleted": result.deleted,
                "total": result.total,
                "skipped": result.skipped,
            }
        finally:
            store.delete(source_ref)
