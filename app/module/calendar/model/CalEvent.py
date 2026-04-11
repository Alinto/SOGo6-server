from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ShowAs import ShowAs


@dataclass
class CalEvent:  # pylint: disable=too-many-instance-attributes
    """
    Format-agnostic representation of a calendar event.
    """
    # RFC 5545 §3.8.4.7
    uid: str
    # RFC 5545 §3.8.1.12 (SUMMARY)
    title: str
    # RFC 5545 §3.8.2.4 (DTSTART)
    start_date: datetime
    # RFC 5545 §3.8.2.2 (DTEND)
    end_date: datetime

    # Internal — database primary key
    id: str | None = None
    # Internal — parent calendar identifier
    calendar_id: str | None = None
    # RFC 5545 §3.3.4 — DATE value type vs DATE-TIME
    all_day: bool = False
    # RFC 5545 §3.2.19 (TZID parameter)
    timezone: str = "UTC"

    # RFC 5545 §3.8.1.5 (DESCRIPTION)
    description: str | None = None
    # RFC 5545 §3.8.1.7 (LOCATION)
    location: str | None = None
    # RFC 5545 §3.8.8.3 (URL)
    url: str | None = None
    # RFC 5545 §3.8.1.11 (STATUS — CONFIRMED, TENTATIVE, CANCELLED)
    status: EventStatus = field(default=EventStatus.CONFIRMED)
    # RFC 5545 §3.8.1.3 (CLASS — PUBLIC, PRIVATE, CONFIDENTIAL)
    visibility: EventVisibility = field(default=EventVisibility.PUBLIC)
    # RFC 5545 §3.8.2.7 (TRANSP — OPAQUE/TRANSPARENT maps to BUSY/FREE);
    # TENTATIVE and OUT_OF_OFFICE are Microsoft extensions (X-MICROSOFT-CDO-BUSYSTATUS)
    show_as: ShowAs = field(default=ShowAs.BUSY)
    # RFC 7986 §5.9 (COLOR) — extension to RFC 5545; also used by Apple Calendar and Google Calendar
    color: str | None = None
    # RFC 5545 §3.8.7.4 (SEQUENCE)
    sequence: int = 0

    # RFC 5545 §3.8.4.3 (ORGANIZER)
    organizer: CalOrganizer | None = None
    # RFC 5545 §3.8.4.1 (ATTENDEE)
    attendees: list[CalAttendee] = field(default_factory=list)
    # RFC 5545 §3.6.6 (VALARM)
    reminders: list[CalReminder] = field(default_factory=list)
    # RFC 5545 §3.8.1.1 (ATTACH)
    attachments: list[CalAttachment] = field(default_factory=list)
    # Google Calendar API (conferenceData) — no RFC basis
    conference_data: CalConferenceData | None = None
    # RFC 5545 §3.8.1.2 (CATEGORIES)
    categories: list[str] = field(default_factory=list)
    # RFC 5545 §3.8.4.5 (RELATED-TO)
    related_to: list[CalEventRelation] = field(default_factory=list)

    # RFC 5545 §3.8.5.3 (RRULE)
    recurrence_rule: CalRecurrenceRule | None = None
    # RFC 5545 §3.8.5.1 (EXDATE)
    recurrence_exceptions: list[datetime] = field(default_factory=list)
    # RFC 5545 §3.8.4.4 (RECURRENCE-ID)
    recurrence_id: datetime | None = None
    # Internal — UID of the master event for detached occurrences
    parent_uid: str | None = None

    # Catch-all for X-* and other non-standard properties
    extra_properties: dict[str, str] = field(default_factory=dict)

    # RFC 5545 §3.8.7.1 (CREATED)
    created_at: datetime | None = None
    # RFC 5545 §3.8.7.3 (LAST-MODIFIED)
    updated_at: datetime | None = None
