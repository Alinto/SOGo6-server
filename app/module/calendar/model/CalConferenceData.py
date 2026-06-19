from __future__ import annotations

from dataclasses import dataclass, field

from app.module.calendar.model.CalConferenceEntryPoint import CalConferenceEntryPoint


@dataclass
class CalConferenceData:
    """
    Conference call information attached to a calendar event.

    Not defined by any RFC - modelled after the Google Calendar API conferenceData object.
    Stored in the cal_event JSON blob; never used in SQL filtering.
    """
    # Provider identifier, e.g. "zoom", "meet", "teams"
    type: str
    # Join URL for the conference
    url: str | None = None
    # Provider-assigned conference identifier
    conference_id: str | None = None
    # One entry point per dial-in method (video, phone, sip...)
    entry_points: list[CalConferenceEntryPoint] = field(default_factory=list)
