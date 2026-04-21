from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalConferenceEntryPoint import CalConferenceEntryPoint
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.serializer.CalendarEventDeserializer import CalendarEventDeserializer
from app.utils.logger.logger import logger_calendar


class CalendarEventDeserializerJson(CalendarEventDeserializer):
    """
    Deserializes JSON (SOGo6 REST API schema) into CalEvent objects.
    Datetimes must be ISO 8601 UTC strings (e.g. 2026-03-19T09:30:00.000Z).
    Enum values are expected as lowercase strings matching the enum .value.
    Missing optional fields default to None or empty lists.
    """

    def deserialize(self, text: str) -> CalEvent:
        """Deserialize a JSON string into a CalEvent."""
        data: dict[str, Any] = json.loads(text)
        return self.from_dict(data)

    def from_dict(self, data: dict[str, Any]) -> CalEvent:
        """Convert a plain dict (REST API schema) into a CalEvent."""
        organizer_raw = data.get("organizer")
        conference_raw = data.get("conference_data")

        return CalEvent(
            id=data.get("id"),
            calendar_id=data.get("calendar_id"),
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
            created_at=self._parse_dt_opt(data.get("created_at")),
            updated_at=self._parse_dt_opt(data.get("updated_at")),
            component_type=self._parse_enum(ComponentType, data.get("component_type"), ComponentType.EVENT),
            percent_complete=data.get("percent_complete"),
            completed_at=self._parse_dt_opt(data.get("completed_at")),
        )

    # ------------------------------------------------------------------
    # Sub-object parsers
    # ------------------------------------------------------------------

    def _parse_organizer(self, data: dict[str, Any]) -> CalOrganizer:
        return CalOrganizer(
            email=data["email"],
            name=data.get("name"),
            role=self._parse_enum(AttendeeRole, data.get("role"), None),
            status=self._parse_enum(AttendeeStatus, data.get("status"), None),
        )

    @staticmethod
    def _parse_attendee(data: dict[str, Any]) -> CalAttendee:
        return CalAttendee(
            email=data["email"],
            name=data.get("name"),
            role=AttendeeRole(data["role"]) if "role" in data else AttendeeRole.REQUIRED,
            status=AttendeeStatus(data["status"]) if "status" in data else AttendeeStatus.NEEDS_ACTION,
            rsvp=data.get("rsvp", False),
        )

    @staticmethod
    def _parse_reminder(data: dict[str, Any]) -> CalReminder:
        return CalReminder(
            method=ReminderMethod(data["method"]),
            minutes_before=data["minutes_before"],
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
            type=data["type"],
            url=data.get("url"),
            conference_id=data.get("conference_id"),
            entry_points=entry_points,
        )

    # ------------------------------------------------------------------
    # Value parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        """Parse an ISO 8601 UTC string into a timezone-aware UTC datetime."""
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

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
