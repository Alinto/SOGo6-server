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
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.CalendarConst import (DEFAULT_REMINDER_MINUTES, MAX_EVENT_DESCRIPTION_LENGTH,
                                               MAX_EVENT_DURATION_HOURS, MAX_EVENT_ALL_DAY_DURATION_HOURS,
                                               MAX_EVENT_LOCATION_LENGTH, MAX_EVENT_TITLE_LENGTH)
from app.utils import errors as err
from app.utils.exceptions import BugException, RequestException


@dataclass
class CalEvent:  # pylint: disable=too-many-instance-attributes,invalid-name,too-many-public-methods
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

    # Internal - database primary key, never exposed in the API
    db_id: int | None = None
    # Opaque public identifier exposed in the API (JSON field "key")
    key: str | None = None
    # UUID key of the parent calendar - stored in DB and exposed in the API
    calendar_key: str | None = None
    # IANA timezone of the parent calendar - transient, not persisted, set by CalendarSource
    calendar_timezone: str | None = None
    # Domain type of the component - drives serialization dispatch
    component_type: ComponentType = ComponentType.UNDEFINED
    # RFC 5545 §3.3.4 - DATE value type vs DATE-TIME
    all_day: bool | None = None
    # RFC 5545 §3.2.19 (TZID parameter)
    timezone: str = "UTC"

    # RFC 5545 §3.8.1.5 (DESCRIPTION)
    description: str | None = None
    # RFC 5545 §3.8.1.7 (LOCATION)
    location: str | None = None
    # RFC 5545 §3.8.8.3 (URL)
    url: str | None = None
    # RFC 5545 §3.8.1.11 (STATUS - CONFIRMED, TENTATIVE, CANCELLED)
    status: EventStatus = field(default=EventStatus.UNDEFINED)
    # RFC 5545 §3.8.1.3 (CLASS - PUBLIC, PRIVATE, CONFIDENTIAL)
    visibility: EventVisibility = field(default=EventVisibility.UNDEFINED)
    # RFC 5545 §3.8.2.7 (TRANSP - OPAQUE/TRANSPARENT maps to BUSY/FREE)
    show_as: ShowAs = field(default=ShowAs.UNDEFINED)
    # RFC 7986 §5.9 (COLOR)
    color: str | None = None
    # RFC 5545 §3.8.7.4 (SEQUENCE)
    sequence: int = 0
    # RFC 5545 §3.8.1.9 (PRIORITY) - 0 = undefined, 1 = highest, 9 = lowest
    priority: int = 0
    # RFC 5545 §3.7.3 (DTSTAMP) - required in every component
    dtstamp: datetime | None = None

    # RFC 5545 §3.8.4.3 (ORGANIZER)
    organizer: CalOrganizer | None = None
    # RFC 5545 §3.8.4.1 (ATTENDEE)
    attendees: list[CalAttendee] = field(default_factory=list)
    # RFC 5545 §3.6.6 (VALARM)
    reminders: list[CalReminder] = field(default_factory=list)
    # RFC 5545 §3.8.1.1 (ATTACH)
    attachments: list[CalAttachment] = field(default_factory=list)
    # Google Calendar API (conferenceData) - no RFC basis
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
    # RFC 5545 §3.8.5.3 RANGE=THISANDFUTURE - None or 'THISANDFUTURE'
    recurrence_range: str | None = None
    # UID of the original series this event was split from (THISANDFUTURE operation).
    # Set on the new master created during a split so the history is traceable.
    # Never used for business logic - informational only, serialized to iCal as
    # RELATED-TO;RELTYPE=X-SOGO-SPLIT-FROM per the SOGo 6 extension.
    uid_parent_split: str | None = None

    # RFC 5545 §3.8.1.8 (PERCENT-COMPLETE) - VTODO only
    percent_complete: int | None = None
    # RFC 5545 §3.8.2.1 (COMPLETED) - VTODO only
    completed_at: datetime | None = None

    # Catch-all for X-* and other non-standard properties
    extra_properties: dict[str, str] = field(default_factory=dict)

    # RFC 5545 §3.8.7.1 (CREATED)
    created_at: datetime | None = None
    # RFC 5545 §3.8.7.3 (LAST-MODIFIED)
    updated_at: datetime | None = None

    # Fields that can be modified by a partial update.
    _MUTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "title", "description", "location", "url", "date_start", "date_end",
        "all_day", "timezone", "status", "visibility", "show_as", "color",
        "sequence", "priority", "organizer", "attendees", "reminders", "conference_data",
        "attachments", "categories", "related_to", "extra_properties",
        "recurrence_rule", "recurrence_exceptions", "percent_complete", "completed_at",
    })

    # Fields computed at serialization time - never persisted in the DB blob.
    _UNPERSISTED_FIELDS: ClassVar[frozenset[str]] = frozenset({"dates_with_tz"})

    # Fields propagated from the organizer's copy to attendee copies on event update.
    # Excludes reminders and conference_data - each attendee manages their own.
    _PROPAGATABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "title", "description", "location", "url", "date_start", "date_end",
        "all_day", "timezone", "status", "visibility", "show_as", "color",
        "sequence", "organizer", "attendees", "attachments", "categories",
        "related_to", "extra_properties", "recurrence_rule", "recurrence_exceptions", "priority",
    })

    # Fields each attendee owns on their own copy (their VALARM and conference data). An attendee who
    # is not the organizer may edit only these; the organizer never propagates them (RFC 6638 §3.2.1).
    _PERSONAL_FIELDS: ClassVar[frozenset[str]] = frozenset({"reminders", "conference_data"})

    def apply_defaults(
        self,
        default_visibility: EventVisibility | None = None,
        default_duration_min: int | None = None,
    ) -> None:
        """Fill in creation-time defaults for fields left at their UNDEFINED/None sentinel.

        The parent calendar's own defaults take precedence over the global fallbacks:
        default_visibility for the CLASS, default_duration_min to derive a missing DTEND.
        Pass None on either to fall back to the global default. Reminder offsets and the
        all-day DTEND invariant are resolved later, at the persistence boundary
        (CalendarSourceDb), so they apply to updates too.
        """
        if self.component_type == ComponentType.UNDEFINED:
            self.component_type = ComponentType.EVENT
        if self.status == EventStatus.UNDEFINED:
            self.status = EventStatus.CONFIRMED
        if self.visibility == EventVisibility.UNDEFINED:
            self.visibility = default_visibility or EventVisibility.PUBLIC
        if self.show_as == ShowAs.UNDEFINED:
            self.show_as = ShowAs.BUSY
        if self.all_day is None:
            self.all_day = False
        self._apply_default_duration(default_duration_min)

    def normalize_all_day(self) -> None:
        """Ensure an all-day event has a valid exclusive DTEND (RFC 5545 §3.6.1).

        For all-day events DTEND must be strictly greater than DTSTART; if it is not,
        advance it to date_start + 1 day. Idempotent once the invariant holds.
        """
        if self.all_day and self.date_end is not None and self.date_start is not None and self.date_end <= self.date_start:
            self.date_end = self.date_start + timedelta(days=1)

    def _apply_default_duration(self, default_duration_min: int | None) -> None:
        """Derive a missing DTEND from a calendar default duration, for timed events only.

        Skipped for tasks/journals (DUE is legitimately optional), all-day events (a
        minute-based duration is meaningless) and events that already carry an end.
        """
        if default_duration_min is None:
            return
        if self.component_type != ComponentType.EVENT:
            return
        if self.all_day or self.date_start is None or self.date_end is not None:
            return
        self.date_end = self.date_start + timedelta(minutes=default_duration_min)

    def resolve_reminder_offsets(self, default_minutes: int | None) -> None:
        """Fill reminders left without an explicit offset using the calendar default, or the global fallback."""
        fallback: int = default_minutes if default_minutes is not None else DEFAULT_REMINDER_MINUTES
        for reminder in self.reminders:
            if reminder.minutes_before is None:
                reminder.minutes_before = fallback

    def validate(self) -> None:
        """Run business validations. Raises RequestException on failure."""
        if self.component_type == ComponentType.EVENT and self.date_end is None:
            raise RequestException(error=err.ERROR_CALENDAR_JSON_PARSE_FAILED)
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

    def is_organized_by(self, email: str) -> bool:
        """True when this event's ORGANIZER matches the given email (False when no organizer)."""
        return self.organizer is not None and self.organizer.email == email

    def attendance_status_for(self, email: str) -> AttendeeStatus | None:
        """Return the participation status of the attendee matching email, or None if not an attendee."""
        for attendee in self.attendees:
            if attendee.email == email:
                return attendee.status
        return None

    def is_attending(self, email: str) -> bool:
        """True unless email is an attendee who has not committed (declined / needs-action / delegated).

        The organizer and anyone absent from the attendee list (a personal event) count as attending;
        an attendee counts only once they have accepted or tentatively accepted. Used to decide whether
        a reminder should fire for this copy's owner.
        """
        status: AttendeeStatus | None = self.attendance_status_for(email)
        return status is None or status in (AttendeeStatus.ACCEPTED, AttendeeStatus.TENTATIVE)

    @property
    def require_uid(self) -> str:
        """UID, guaranteed on any persisted or fully-built event (RFC 5545 requires it)."""
        if self.uid is None:
            raise BugException("CalEvent.uid accessed before it was set")
        return self.uid

    @property
    def require_key(self) -> str:
        """Opaque public key, guaranteed once the event has been persisted/loaded."""
        if self.key is None:
            raise BugException("CalEvent.key accessed before the event was persisted")
        return self.key

    @property
    def require_calendar_key(self) -> str:
        """Parent calendar key, guaranteed once the event is attached to a calendar."""
        if self.calendar_key is None:
            raise BugException("CalEvent.calendar_key accessed before the event was attached")
        return self.calendar_key

    @property
    def require_date_start(self) -> datetime:
        """Start datetime, guaranteed on any scheduled component (RFC 5545 DTSTART)."""
        if self.date_start is None:
            raise BugException("CalEvent.date_start accessed before it was set")
        return self.date_start

    @property
    def require_date_end(self) -> datetime:
        """End datetime, guaranteed for a VEVENT (DTEND). A VTODO may have none (no DUE)."""
        if self.date_end is None:
            raise BugException("CalEvent.date_end accessed before it was set")
        return self.date_end

    @property
    def duration(self) -> timedelta:
        """Span from start to end/due. Zero when there is no end (e.g. a task without a due date)."""
        if self.date_start is None or self.date_end is None:
            return timedelta(0)
        return self.date_end - self.date_start

    @property
    def require_recurrence_id(self) -> datetime:
        """Recurrence id, guaranteed on a detached occurrence (RFC 5545 RECURRENCE-ID)."""
        if self.recurrence_id is None:
            raise BugException("CalEvent.recurrence_id accessed on a non-detached event")
        return self.recurrence_id

    def apply_update(self, updates: dict[str, Any]) -> None:
        """Apply a partial update dict to this event, ignoring unknown or immutable fields."""
        for field_name, value in updates.items():
            if field_name in self._MUTABLE_FIELDS:
                setattr(self, field_name, value)

    @staticmethod
    def is_mutable_field(field_name: str) -> bool:
        """Return True if the field accepts partial updates."""
        return field_name in CalEvent._MUTABLE_FIELDS

    @staticmethod
    def strip_unpersisted_fields(blob: dict[str, Any]) -> None:
        """Drop fields that are computed at serialization time from a DB blob, in place."""
        for field_name in CalEvent._UNPERSISTED_FIELDS:
            blob.pop(field_name, None)

    def _copy_fields(self, source: CalEvent, field_names: frozenset[str]) -> None:
        for field_name in field_names:
            setattr(self, field_name, getattr(source, field_name))

    def apply_personal_fields(self, source: CalEvent) -> None:
        """Copy the attendee-owned fields (VALARM, conference data) from another copy."""
        self._copy_fields(source, self._PERSONAL_FIELDS)

    def apply_propagatable_fields(self, source: CalEvent) -> None:
        """Copy the organizer-controlled fields from the master copy onto an attendee copy."""
        self._copy_fields(source, self._PROPAGATABLE_FIELDS)

    def apply_organizer_content(self, source: CalEvent) -> None:
        """Copy the shared content fields from an organizer update, leaving personal fields untouched."""
        self._copy_fields(source, self._MUTABLE_FIELDS - self._PERSONAL_FIELDS)

    def has_content_changes(self, other: CalEvent) -> bool:
        """Return True if any mutable field differs from the other event."""
        return any(getattr(self, field_name) != getattr(other, field_name) for field_name in self._MUTABLE_FIELDS)

    def has_organizer_content_changes(self, other: CalEvent) -> bool:
        """Return True if any organizer-owned content field differs (attendee-personal fields excluded)."""
        return any(getattr(self, field_name) != getattr(other, field_name)
                   for field_name in self._MUTABLE_FIELDS - self._PERSONAL_FIELDS)

    def has_scheduling_changes(self, other: CalEvent) -> bool:
        """Return True if a field that requires attendees to re-confirm differs (RFC 5546 significant change).

        A reschedule of the start/end, all-day flag, timezone or recurrence pattern invalidates prior
        replies; cosmetic edits (title, description, ...) do not.
        """
        scheduling_fields: tuple[str, ...] = (
            "date_start", "date_end", "all_day", "timezone", "recurrence_rule", "recurrence_exceptions",
        )
        return any(getattr(self, field_name) != getattr(other, field_name) for field_name in scheduling_fields)

    def reset_attendee_responses(self) -> None:
        """Reset every non-organizer attendee's PARTSTAT to NEEDS-ACTION and request a fresh reply.

        Called after a significant change so attendees must re-confirm (RFC 5546 §2.1.4). The
        organizer's own entry, implicitly accepted, is left untouched.
        """
        for attendee in self.attendees:
            if self.organizer is not None and attendee.email == self.organizer.email:
                continue
            attendee.status = AttendeeStatus.NEEDS_ACTION
            attendee.rsvp = True
