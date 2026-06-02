from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, ClassVar

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.CalendarConst import (MAX_EVENT_DESCRIPTION_LENGTH, MAX_EVENT_DURATION_HOURS,
                                               MAX_EVENT_ALL_DAY_DURATION_HOURS,
                                               MAX_EVENT_LOCATION_LENGTH, MAX_EVENT_TITLE_LENGTH)
from app.utils import errors as err
from app.utils.exceptions import RequestException


@dataclass
class CalEvent:  # pylint: disable=too-many-instance-attributes,invalid-name
    """
    Format-agnostic representation of a calendar event/task/journal.
    """
    # RFC 5545 §3.8.4.7
    uid: str | None = None
    # RFC 5545 §3.8.1.12 (SUMMARY)
    title: str | None = None
    # RFC 5545 §3.8.2.4 (DTSTART)
    date_start: datetime | None = None
    # RFC 5545 §3.8.2.2 (DTEND) or DUE (VTODO / TASK)
    date_end: datetime | None = None

    # Internal — database primary key, never exposed in the API
    db_id: int | None = None
    # Opaque public identifier exposed in the API (JSON field "key")
    key: str | None = None
    # UUID key of the parent calendar — stored in DB and exposed in the API
    calendar_key: str | None = None
    # IANA timezone of the parent calendar — transient, not persisted, set by CalendarSource
    calendar_timezone: str | None = None
    # Domain type of the component — drives serialization dispatch
    component_type: ComponentType = ComponentType.UNDEFINED
    # RFC 5545 §3.3.4 — DATE value type vs DATE-TIME
    all_day: bool | None = None
    # RFC 5545 §3.2.19 (TZID parameter)
    timezone: str = "UTC"

    # RFC 5545 §3.8.1.5 (DESCRIPTION)
    description: str | None = None
    # RFC 5545 §3.8.1.7 (LOCATION)
    location: str | None = None
    # RFC 5545 §3.8.8.3 (URL)
    url: str | None = None
    # RFC 5545 §3.8.1.11 (STATUS — CONFIRMED, TENTATIVE, CANCELLED)
    status: EventStatus = field(default=EventStatus.UNDEFINED)
    # RFC 5545 §3.8.1.3 (CLASS — PUBLIC, PRIVATE, CONFIDENTIAL)
    visibility: EventVisibility = field(default=EventVisibility.UNDEFINED)
    # RFC 5545 §3.8.2.7 (TRANSP — OPAQUE/TRANSPARENT maps to BUSY/FREE)
    show_as: ShowAs = field(default=ShowAs.UNDEFINED)
    # RFC 7986 §5.9 (COLOR)
    color: str | None = None
    # RFC 5545 §3.8.7.4 (SEQUENCE)
    sequence: int = 0
    # RFC 5545 §3.8.1.9 (PRIORITY) — 0 = undefined, 1 = highest, 9 = lowest
    priority: int = 0
    # RFC 5545 §3.7.3 (DTSTAMP) — required in every component
    dtstamp: datetime | None = None

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
    # RFC 5545 §3.8.5.3 RANGE=THISANDFUTURE — None or 'THISANDFUTURE'
    recurrence_range: str | None = None
    # UID of the master recurring event — set on detached occurrences (RECURRENCE-ID rows)
    parent_uid: str | None = None
    # UID of the original series this event was split from (THISANDFUTURE operation).
    # Set on the new master created during a split so the history is traceable.
    # Never used for business logic — informational only, serialized to iCal as
    # RELATED-TO;RELTYPE=X-SOGO-SPLIT-FROM per the SOGo 6 extension.
    uid_parent_split: str | None = None

    # RFC 5545 §3.8.1.8 (PERCENT-COMPLETE) — VTODO only
    percent_complete: int | None = None
    # RFC 5545 §3.8.2.1 (COMPLETED) — VTODO only
    completed_at: datetime | None = None

    # Catch-all for X-* and other non-standard properties
    extra_properties: dict[str, str] = field(default_factory=dict)

    # RFC 5545 §3.8.7.1 (CREATED)
    created_at: datetime | None = None
    # RFC 5545 §3.8.7.3 (LAST-MODIFIED)
    updated_at: datetime | None = None

    # Fields that can be modified by a partial update. Used by apply_update and
    # RecurrenceScopeProcessor to determine which fields to merge.
    MUTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "title", "description", "location", "url", "date_start", "date_end",
        "all_day", "timezone", "status", "visibility", "show_as", "color",
        "sequence", "priority", "organizer", "attendees", "reminders", "conference_data",
        "attachments", "categories", "related_to", "extra_properties",
        "recurrence_rule", "recurrence_exceptions", "percent_complete", "completed_at",
    })

    # Fields computed at serialization time — never persisted in the DB blob.
    UNPERSISTED_FIELDS: ClassVar[frozenset[str]] = frozenset({"dates_with_tz"})

    # Fields propagated from the organizer's copy to attendee copies on event update.
    # Excludes reminders and conference_data — each attendee manages their own.
    PROPAGATABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "title", "description", "location", "url", "date_start", "date_end",
        "all_day", "timezone", "status", "visibility", "show_as", "color",
        "sequence", "organizer", "attendees", "attachments", "categories",
        "related_to", "extra_properties", "recurrence_rule", "recurrence_exceptions", "priority",
    })

    def apply_defaults(self) -> None:
        """Fill in business defaults for fields left at their UNDEFINED/None sentinel.

        Called before persisting to ensure all relational columns have valid values.
        """
        if self.component_type == ComponentType.UNDEFINED:
            self.component_type = ComponentType.EVENT
        if self.status == EventStatus.UNDEFINED:
            self.status = EventStatus.CONFIRMED
        if self.visibility == EventVisibility.UNDEFINED:
            self.visibility = EventVisibility.PUBLIC
        if self.show_as == ShowAs.UNDEFINED:
            self.show_as = ShowAs.BUSY
        if self.all_day is None:
            self.all_day = False

    def validate(self) -> None:
        """Run business validations. Raises RequestException on failure."""
        if not self.all_day and self.date_start is not None and self.date_end is not None:
            if (self.date_end - self.date_start) > timedelta(hours=MAX_EVENT_DURATION_HOURS):
                raise RequestException(error=err.ERROR_CALENDAR_EVENT_DURATION_TOO_LONG)
        if self.all_day and self.date_start is not None and self.date_end is not None:
            if (self.date_end - self.date_start) > timedelta(hours=MAX_EVENT_ALL_DAY_DURATION_HOURS):
                raise RequestException(error=err.ERROR_CALENDAR_EVENT_DURATION_TOO_LONG)
        if self.title and len(self.title) > MAX_EVENT_TITLE_LENGTH:
            raise RequestException(error=err.ERROR_CALENDAR_JSON_PARSE_FAILED)
        if self.description and len(self.description) > MAX_EVENT_DESCRIPTION_LENGTH:
            raise RequestException(error=err.ERROR_CALENDAR_JSON_PARSE_FAILED)
        if self.location and len(self.location) > MAX_EVENT_LOCATION_LENGTH:
            raise RequestException(error=err.ERROR_CALENDAR_JSON_PARSE_FAILED)

    def sanitize(self) -> None:
        """Truncate oversized text fields to their maximum allowed length. Used for external ICS imports."""
        if self.title and len(self.title) > MAX_EVENT_TITLE_LENGTH:
            self.title = self.title[:MAX_EVENT_TITLE_LENGTH]
        if self.description and len(self.description) > MAX_EVENT_DESCRIPTION_LENGTH:
            self.description = self.description[:MAX_EVENT_DESCRIPTION_LENGTH]
        if self.location and len(self.location) > MAX_EVENT_LOCATION_LENGTH:
            self.location = self.location[:MAX_EVENT_LOCATION_LENGTH]

    @property
    def is_detached(self) -> bool:
        """True when this is a detached occurrence (has recurrence_id but no recurrence_rule)."""
        return self.recurrence_id is not None and self.recurrence_rule is None

    def apply_update(self, updates: dict[str, Any]) -> None:
        """Apply a partial update dict to this event, ignoring unknown or immutable fields."""
        for field_name, value in updates.items():
            if field_name in self.MUTABLE_FIELDS:
                setattr(self, field_name, value)
