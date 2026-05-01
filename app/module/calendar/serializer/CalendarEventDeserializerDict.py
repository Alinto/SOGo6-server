from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalConferenceEntryPoint import CalConferenceEntryPoint
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.RelationType import RelationType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.serializer.CalendarEventDeserializer import CalendarEventDeserializer
from app.utils.logger.logger import logger_calendar


_SKIP = object()


class CalendarEventDeserializerDict(CalendarEventDeserializer[dict]):
    """Deserializes plain dicts into CalEvent objects.

    Handles both full dicts (event creation) and partial dicts (event update).
    Fields absent from the dict are left as None on the resulting CalEvent.
    """

    def deserialize(self, data: dict[str, Any]) -> CalEvent:
        """Convert a dict into a CalEvent.

        Fields present in the dict are parsed and set. Fields absent from the dict
        keep the CalEvent dataclass default. uid, title, date_start, date_end default
        to None when absent (partial update scenario).
        """
        organizer_raw: dict | None = data.get("organizer")
        conference_raw: dict | None = data.get("conference_data")

        return CalEvent(
            key=data.get("key"),
            calendar_key=data.get("calendar_key"),
            uid=data.get("uid"),
            title=data.get("title"),
            description=data.get("description"),
            location=data.get("location"),
            date_start=self._parse_dt(data["date_start"]) if "date_start" in data else None,
            date_end=self._parse_dt(data["date_end"]) if "date_end" in data else None,
            all_day=data.get("all_day", False),
            timezone=data.get("timezone") or "UTC",
            status=self._parse_enum(EventStatus, data.get("status"), EventStatus.CONFIRMED),
            visibility=self._parse_enum(EventVisibility, data.get("visibility"), EventVisibility.PUBLIC),
            show_as=self._parse_enum(ShowAs, data.get("show_as"), ShowAs.BUSY),
            color=data.get("color"),
            sequence=data.get("sequence", 0),
            organizer=self._parse_organizer(organizer_raw) if organizer_raw else None,
            attendees=[self._parse_attendee(a) for a in data.get("attendees", [])],
            reminders=[self._parse_reminder(r) for r in data.get("reminders", [])],
            conference_data=self._parse_conference(conference_raw) if conference_raw else None,
            attachments=[self._parse_attachment(a) for a in data.get("attachments", [])],
            url=data.get("url"),
            categories=data.get("categories", []),
            related_to=[self._parse_relation(r) for r in data.get("related_to", [])],
            extra_properties=data.get("extra_properties", {}),
            priority=data.get("priority", 0),
            component_type=self._parse_enum(ComponentType, data.get("component_type"), ComponentType.EVENT),
            percent_complete=data.get("percent_complete"),
            completed_at=self._parse_dt_opt(data.get("completed_at")),
            recurrence_rule=self._parse_recurrence_rule(data.get("recurrence_rule")),
            recurrence_exceptions=[self._parse_dt(d) for d in data.get("recurrence_exceptions", [])],
            recurrence_id=self._parse_dt_opt(data.get("recurrence_id")),
            recurrence_range=data.get("recurrence_range"),
            parent_uid=data.get("parent_uid"),
            uid_parent_split=data.get("uid_parent_split"),
        )

    def deserialize_with_update(self, origin: CalEvent, update: dict | CalEvent) -> CalEvent:
        """Apply an update to an existing CalEvent and return the result.

        When update is a dict, parse each key and apply it to a copy of origin.
        Only keys present in the dict are modified — other fields keep origin's values.
        When update is a CalEvent, return it directly (full replacement).
        """
        if isinstance(update, CalEvent):
            return update

        merged: CalEvent = dataclasses.replace(origin)
        for key, raw_value in update.items():
            parsed = self._parse_field(key, raw_value)
            if parsed is not _SKIP:
                setattr(merged, key, parsed)
        return merged

    def _parse_field(self, key: str, value: Any) -> Any:  # pylint: disable=too-many-return-statements,too-many-branches
        """Parse a single field value from a dict. Returns _SKIP for unknown fields."""
        if key == "recurrence_rule":
            return self._parse_recurrence_rule(value)
        if key == "recurrence_exceptions":
            return [self._parse_dt(d) for d in value]
        if key in ("date_start", "date_end"):
            return self._parse_dt(value)
        if key in ("completed_at", "recurrence_id"):
            return self._parse_dt_opt(value)
        if key == "attendees":
            return [self._parse_attendee(a) for a in value]
        if key == "reminders":
            return [self._parse_reminder(r) for r in value]
        if key == "organizer":
            return self._parse_organizer(value) if value else None
        if key == "conference_data":
            return self._parse_conference(value) if value else None
        if key == "attachments":
            return [self._parse_attachment(a) for a in value]
        if key == "related_to":
            return [self._parse_relation(r) for r in value]
        if key == "status":
            return self._parse_enum(EventStatus, value, EventStatus.CONFIRMED)
        if key == "visibility":
            return self._parse_enum(EventVisibility, value, EventVisibility.PUBLIC)
        if key == "show_as":
            return self._parse_enum(ShowAs, value, ShowAs.BUSY)
        if key == "component_type":
            return self._parse_enum(ComponentType, value, ComponentType.EVENT)
        if key == "timezone":
            return value or None
        if key in CalEvent.MUTABLE_FIELDS or key == "recurrence_range":
            return value
        return _SKIP

    def _parse_organizer(self, data: dict[str, Any]) -> CalOrganizer:
        return CalOrganizer(
            email=data.get("email", ""),
            name=data.get("name"),
            role=self._parse_enum(AttendeeRole, data.get("role"), None),
            status=self._parse_enum(AttendeeStatus, data.get("status"), None),
            sent_by=data.get("sent_by"),
            dir_ref=data.get("dir_ref"),
        )

    @staticmethod
    def _parse_attendee(data: dict[str, Any]) -> CalAttendee:
        return CalAttendee(
            email=data.get("email", ""),
            name=data.get("name"),
            role=AttendeeRole(data["role"]) if "role" in data else AttendeeRole.REQUIRED,
            status=AttendeeStatus(data["status"]) if "status" in data else AttendeeStatus.NEEDS_ACTION,
            rsvp=data.get("rsvp", False),
            cutype=CalUserType(data["cutype"]) if "cutype" in data else CalUserType.INDIVIDUAL,
            delegated_from=data.get("delegated_from"),
            delegated_to=data.get("delegated_to"),
            sent_by=data.get("sent_by"),
            dir_ref=data.get("dir_ref"),
        )

    @staticmethod
    def _parse_reminder(data: dict[str, Any]) -> CalReminder:
        return CalReminder(
            method=ReminderMethod(data.get("method", "display")),
            minutes_before=data.get("minutes_before", 15),
        )

    @staticmethod
    def _parse_attachment(data: dict[str, Any]) -> CalAttachment:
        return CalAttachment(
            filename=data.get("filename"),
            mime_type=data.get("mime_type"),
            url=data.get("url"),
            size=data.get("size"),
        )

    @staticmethod
    def _parse_conference(data: dict[str, Any]) -> CalConferenceData:
        entry_points = [
            CalConferenceEntryPoint(
                type=ep["type"],
                uri=ep["uri"],
                label=ep.get("label"),
            )
            for ep in data.get("entry_points", [])
        ]
        return CalConferenceData(
            type=data.get("type", ""),
            url=data.get("url"),
            conference_id=data.get("conference_id"),
            entry_points=entry_points,
        )

    @staticmethod
    def _parse_relation(data: dict[str, Any]) -> CalEventRelation:
        return CalEventRelation(
            uid=data.get("uid", ""),
            relation_type=RelationType(data["relation_type"]) if "relation_type" in data else RelationType.PARENT,
        )



    def _parse_recurrence_rule(self, data: dict[str, Any] | None) -> CalRecurrenceRule | None:
        if data is None:
            return None
        return CalRecurrenceRule(
            frequency=RecurrenceFrequency(data["frequency"]),
            interval=data.get("interval", 1),
            until=self._parse_dt_opt(data.get("until")),
            count=data.get("count"),
            by_day=data.get("by_day"),
            by_month_day=data.get("by_month_day"),
            by_month=data.get("by_month"),
            by_year_day=data.get("by_year_day"),
            by_week_no=data.get("by_week_no"),
            by_set_pos=data.get("by_set_pos"),
            by_hour=data.get("by_hour"),
            by_minute=data.get("by_minute"),
            by_second=data.get("by_second"),
            week_start=data.get("week_start", "MO"),
        )

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        """Parse an ISO 8601 UTC string into a timezone-aware UTC datetime."""
        return datetime.fromisoformat(value).astimezone(timezone.utc)

    def _parse_dt_opt(self, value: str | None) -> datetime | None:
        """Parse an optional ISO 8601 UTC string; return None if absent."""
        return self._parse_dt(value) if value else None

    @staticmethod
    def _parse_enum(enum_cls: type, value: str | None, default: Any) -> Any:
        """Parse an enum from its string value; return default on missing or unknown value."""
        if value is None:
            return default
        try:
            return enum_cls(value)
        except ValueError:
            logger_calendar.warning("Unknown %s value %r, using default %r", enum_cls.__name__, value, default)
            return default
