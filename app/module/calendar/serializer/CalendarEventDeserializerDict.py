from __future__ import annotations

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


class CalendarEventDeserializerDict(CalendarEventDeserializer[dict]):
    """
    Deserializes plain dicts (SOGo6 REST API schema) into CalEvent objects.
    Datetimes must be ISO 8601 UTC strings (e.g. 2026-03-19T09:30:00.000Z).
    Enum values are expected as lowercase strings matching the enum .value.
    Missing optional fields default to None or empty lists.
    """

    def deserialize(self, data: dict[str, Any]) -> CalEvent:
        """Convert a plain dict (REST API schema) into a CalEvent."""
        organizer_raw = data.get("organizer")
        conference_raw = data.get("conference_data")

        return CalEvent(
            key=data.get("key"),
            calendar_key=data.get("calendar_key"),
            uid=data.get("uid", ""),
            title=data.get("title", ""),
            description=data.get("description"),
            location=data.get("location"),
            date_start=self._parse_dt(data["date_start"]),
            date_end=self._parse_dt(data["date_end"]),
            all_day=data.get("all_day", False),
            timezone=data.get("timezone", "UTC"),
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
        )

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

    def parse_patch_fields(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Convert complex nested fields in a PATCH body to their domain model types.

        Only fields present in updates are processed; all others are passed through unchanged.
        This allows partial updates without requiring the full CalEvent field set.
        """
        result = dict(updates)
        if "recurrence_rule" in result:
            result["recurrence_rule"] = self._parse_recurrence_rule(result["recurrence_rule"])
        if "attendees" in result:
            result["attendees"] = [self._parse_attendee(a) for a in result["attendees"]]
        if "reminders" in result:
            result["reminders"] = [self._parse_reminder(r) for r in result["reminders"]]
        if "organizer" in result and result["organizer"]:
            result["organizer"] = self._parse_organizer(result["organizer"])
        if "conference_data" in result and result["conference_data"]:
            result["conference_data"] = self._parse_conference(result["conference_data"])
        if "attachments" in result:
            result["attachments"] = [self._parse_attachment(a) for a in result["attachments"]]
        if "related_to" in result:
            result["related_to"] = [self._parse_relation(r) for r in result["related_to"]]
        if "recurrence_exceptions" in result:
            result["recurrence_exceptions"] = [self._parse_dt(d) for d in result["recurrence_exceptions"]]
        return result

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
