"""Agent task: export a calendar as a VCALENDAR result.

The serialised ICS is offloaded to ``TaskResultLargeStore`` because it can be
sizeable (thousands of events). ``TaskState.result`` only carries the storage
reference plus light metadata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from app.agent.tasks.BaseTask import BaseTask, agent_task
from app.agent.tasks.TaskRequest import TaskRequest
from app.agent.tasks.task_result_large_store.TaskResultLargeStoreFactory import get_large_store
from app.config.settings.ProcessSetting import process_config
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar
from app.utils.calendar.DateTimeUtils import parse_iso


@dataclass
class ExportIcsRequest(TaskRequest):
    """Inputs for an ICS export task.

    ``date_start`` / ``date_end`` are ISO 8601 strings (or ``None`` for unbounded).
    The result is offloaded to ``TaskResultLargeStore`` — its reference lives in
    ``state.result["large_result"]``.
    """

    name: ClassVar[str] = "calendar.export.ics"
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False

    calendar_key: str = ""
    date_start: str | None = None
    date_end: str | None = None

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return asdict(self)


@agent_task
class ExportIcsTask(BaseTask):
    """Worker-side counterpart of :class:`ExportIcsRequest`."""

    request_class = ExportIcsRequest

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, task_id: str,
    ) -> dict[str, Any]:
        """Serialise the requested calendar and store the result blob.

        :param payload: dict produced by ``ExportIcsRequest.payload`` and rehydrated
            here through ``ExportIcsRequest(**payload)``.
        :type payload: dict[str, Any]
        :param user_uid: identity of the calendar owner; ``None`` is rejected because
            an export is always scoped to a user.
        :type user_uid: str | None
        :param task_id: Celery-provided task id. Unused here but kept by contract for
            future per-task tracing.
        :type task_id: str
        :return: ``{"large_result": <ref dict>, "filename": "<key>.ics", "size_bytes": int}``
            where ``large_result`` is the reference dict produced by the configured
            ``TaskResultLargeStore`` backend.
        :rtype: dict[str, Any]
        :raises ValueError: ``user_uid`` is ``None``.
        """
        if user_uid is None:
            raise ValueError("ExportIcsTask requires a user_uid")
        req: ExportIcsRequest = ExportIcsRequest(**payload)
        inter: InterfaceAgentCalendar = InterfaceAgentCalendar(process_config, user_uid)
        ics: str = inter.export_calendar(
            req.calendar_key,
            date_start=parse_iso(req.date_start),
            date_end=parse_iso(req.date_end),
        )
        encoded: bytes = ics.encode("utf-8")
        ref: dict[str, Any] = get_large_store().save(encoded, "text/calendar")
        return {
            "large_result": ref,
            "filename": f"{req.calendar_key}.ics",
            "size_bytes": len(encoded),
        }
