"""In-Redis snapshot of an Agent job across its lifecycle."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agent.AgentConst import JOB_CONCURRENCY_LOCK_PREFIX
from app.agent.jobs.JobStatus import JobStatus
from app.utils.datetime.DateTimeUtils import parse_iso


@dataclass
class JobState:  # pylint: disable=too-many-instance-attributes
    """Source of truth for the admin / user API on the lifecycle of an Agent job.

    Persisted in Redis via :class:`JobPersistency`; populated and updated by the
    Celery lifecycle hooks installed in :meth:`Agent.register_lifecycle_hooks`.
    Carries everything Celery's native ``AsyncResult`` cannot: user ownership,
    payload, attempt counter, the configured ``max_try`` / ``soft_timeout_seconds``
    snapshot at enqueue time, and the optional periodic schedule that produced it.
    """
    job_id: str
    name: str
    status: JobStatus
    # None for system jobs (purge, maintenance) not tied to a user.
    user_uid: str | None

    date_planned: datetime
    date_start: datetime | None = None
    date_end: datetime | None = None
    duration_seconds: float | None = None

    attempts: int = 0
    max_try: int = 0
    soft_timeout_seconds: int = 0
    # Snapshot of the request's max_concurrent: 0 means no concurrency lock was taken.
    max_concurrent: int = 0

    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None

    schedule_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status.value,
            "user_uid": self.user_uid,
            "date_planned": self.date_planned.isoformat(),
            "date_start": self.date_start.isoformat() if self.date_start else None,
            "date_end": self.date_end.isoformat() if self.date_end else None,
            "duration_seconds": self.duration_seconds,
            "attempts": self.attempts,
            "max_try": self.max_try,
            "soft_timeout_seconds": self.soft_timeout_seconds,
            "max_concurrent": self.max_concurrent,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "schedule_name": self.schedule_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobState:
        """Rehydrate from a dict produced by :meth:`to_dict`."""
        planned: datetime | None = parse_iso(data["date_planned"])
        assert planned is not None, "date_planned is required and never None in to_dict()"
        return cls(
            job_id=data["job_id"],
            name=data["name"],
            status=JobStatus(data["status"]),
            user_uid=data.get("user_uid"),
            date_planned=planned,
            date_start=parse_iso(data.get("date_start")),
            date_end=parse_iso(data.get("date_end")),
            duration_seconds=data.get("duration_seconds"),
            attempts=data.get("attempts", 0),
            max_try=data.get("max_try", 0),
            soft_timeout_seconds=data.get("soft_timeout_seconds", 0),
            max_concurrent=data.get("max_concurrent", 0),
            payload=data.get("payload") or {},
            result=data.get("result"),
            error=data.get("error"),
            schedule_name=data.get("schedule_name"),
        )

    @staticmethod
    def concurrency_lock_key(name: str, user_uid: str | None) -> str:
        """Build the lock key that gates concurrent enqueues for a ``(name, user)`` scope.

        ``user_uid`` is the scope when set; otherwise the global slot ``_global``
        (system jobs). The key derives from the job identity, hence its home here.
        """
        return f"{JOB_CONCURRENCY_LOCK_PREFIX}{name}:{user_uid or '_global'}"
