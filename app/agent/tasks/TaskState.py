"""In-Redis snapshot of an Agent task across its lifecycle."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agent.tasks.TaskStatus import TaskStatus
from app.utils.calendar.DateTimeUtils import parse_iso


@dataclass
class TaskState:  # pylint: disable=too-many-instance-attributes
    """Source of truth for the admin/user API. ``schedule_name`` is set for Beat firings."""
    task_id: str
    name: str
    status: TaskStatus
    # None for system tasks (purge, maintenance) not tied to a user.
    user_uid: str | None

    date_planned: datetime
    date_start: datetime | None = None
    date_end: datetime | None = None
    duration_seconds: float | None = None

    attempts: int = 0
    max_try: int = 0
    soft_timeout_seconds: int = 0

    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None

    schedule_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "task_id": self.task_id,
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
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "schedule_name": self.schedule_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        """Rehydrate from a dict produced by :meth:`to_dict`."""
        planned: datetime | None = parse_iso(data["date_planned"])
        assert planned is not None, "date_planned is required and never None in to_dict()"
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            status=TaskStatus(data["status"]),
            user_uid=data.get("user_uid"),
            date_planned=planned,
            date_start=parse_iso(data.get("date_start")),
            date_end=parse_iso(data.get("date_end")),
            duration_seconds=data.get("duration_seconds"),
            attempts=data.get("attempts", 0),
            max_try=data.get("max_try", 0),
            soft_timeout_seconds=data.get("soft_timeout_seconds", 0),
            payload=data.get("payload") or {},
            result=data.get("result"),
            error=data.get("error"),
            schedule_name=data.get("schedule_name"),
        )
