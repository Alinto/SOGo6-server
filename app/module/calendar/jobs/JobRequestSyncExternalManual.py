"""Request DTO for the manual external-calendar sync job.

Standalone (not co-located with ``JobSyncExternalManual``) so ``ModuleCalendar`` can import it at
module level to enqueue, without pulling the worker side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest


@dataclass
class JobRequestSyncExternalManual(JobRequest):
    """Inputs for a user-triggered sync of a single external ICS calendar."""

    name: ClassVar[str] = "calendar.sync.external.manual"
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False
    # No per-user concurrency gate: same-calendar dedup is handled by the SyncEngine Redis lock,
    # so a user can sync several different calendars at once.
    max_concurrent: ClassVar[int] = 0

    calendar_key: str = ""

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return {"calendar_key": self.calendar_key}
