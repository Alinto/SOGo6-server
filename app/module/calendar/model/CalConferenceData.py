from __future__ import annotations

from dataclasses import dataclass, field

from app.module.calendar.model.CalConferenceEntryPoint import CalConferenceEntryPoint


@dataclass
class CalConferenceData:
    """
    Conference call information associated with a calendar event.
    """
    type: str
    url: str | None = None
    conference_id: str | None = None
    entry_points: list[CalConferenceEntryPoint] = field(default_factory=list)
