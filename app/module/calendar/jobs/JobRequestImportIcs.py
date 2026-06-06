"""Request DTO for the ICS import job.

Standalone (not co-located with ``JobImportIcs``) so ``ModuleCalendar`` can
import it at module level to enqueue, without pulling the worker side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest
from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef


@dataclass
class JobRequestImportIcs(JobRequest):
    """Inputs for an ICS import job.

    The uploaded file is offloaded to the large store before enqueue; only its
    reference (``source_ref``) travels in the payload, not the bytes. The reference
    is serialised to a JSON-safe dict for the broker and rebuilt worker-side.
    """

    name: ClassVar[str] = "calendar.import.ics"
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False

    calendar_key: str = ""
    source_ref: JobLargeRef | None = None

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return {
            "calendar_key": self.calendar_key,
            "source_ref": self.source_ref.to_dict() if self.source_ref is not None else None,
        }
