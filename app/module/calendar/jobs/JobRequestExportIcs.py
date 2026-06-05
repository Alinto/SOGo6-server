"""Request DTO for the ICS export job.

Standalone (not co-located with ``JobExportIcs``) on purpose: ``ModuleCalendar``
builds a ``JobRequestExportIcs`` to enqueue the export, while the worker
``JobExportIcs`` depends on ``ModuleCalendar`` through ``InterfaceAgentCalendar``.
Keeping the request free of any worker-side dependency lets ``ModuleCalendar``
import it at module level without an import cycle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest


@dataclass
class JobRequestExportIcs(JobRequest):
    """Inputs for an ICS export job.

    ``date_start`` / ``date_end`` are ISO 8601 strings (or ``None`` for unbounded).
    The result is offloaded to ``JobResultLargeStore`` — its reference lives in
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
