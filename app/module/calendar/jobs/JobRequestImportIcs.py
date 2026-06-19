"""Request DTO for the ICS import job.

Standalone (not co-located with ``JobImportIcs``) so ``ModuleCalendar`` can
import it at module level to enqueue, without pulling the worker side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest


@dataclass
class JobRequestImportIcs(JobRequest):
    """Inputs for an ICS import job.

    The uploaded file is offloaded to the blob store before enqueue; only its
    reference string (``source_ref``) travels in the payload, not the bytes.
    """

    name: ClassVar[str] = "calendar.import.ics"
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False

    calendar_key: str = ""
    source_ref: str | None = None

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return {
            "calendar_key": self.calendar_key,
            "source_ref": self.source_ref,
        }
