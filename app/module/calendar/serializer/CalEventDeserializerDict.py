from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.serializer.CalAttachmentDeserializerDict import CalAttachmentDeserializerDict
from app.module.calendar.serializer.CalAttendeeDeserializerDict import CalAttendeeDeserializerDict
from app.module.calendar.serializer.CalConferenceDataDeserializerDict import CalConferenceDataDeserializerDict
from app.module.calendar.serializer.CalEventRelationDeserializerDict import CalEventRelationDeserializerDict
from app.module.calendar.serializer.CalEventDeserializer import CalEventDeserializer
from app.module.calendar.serializer.CalOrganizerDeserializerDict import CalOrganizerDeserializerDict
from app.module.calendar.serializer.CalRecurrenceRuleDeserializerDict import CalRecurrenceRuleDeserializerDict
from app.module.calendar.serializer.CalReminderDeserializerDict import CalReminderDeserializerDict
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.logger.logger import logger_calendar


_SKIP = object()


class CalEventDeserializerDict(CalEventDeserializer[dict]):
    """Deserializes plain dicts into CalEvent objects.

    Handles both full dicts (event creation) and partial dicts (event update).
    Fields absent from the dict are left as None on the resulting CalEvent.
    Multi-valued sub-objects are delegated to their own deserializers.
    """

    def __init__(self) -> None:
        self._organizer_deserializer = CalOrganizerDeserializerDict()
        self._attendee_deserializer = CalAttendeeDeserializerDict()
        self._reminder_deserializer = CalReminderDeserializerDict()
        self._conference_deserializer = CalConferenceDataDeserializerDict()
        self._relation_deserializer = CalEventRelationDeserializerDict()
        self._attachment_deserializer = CalAttachmentDeserializerDict()
        self._recurrence_deserializer = CalRecurrenceRuleDeserializerDict()

    def deserialize(self, data: dict[str, Any]) -> CalEvent:
        """Convert a dict into a CalEvent.

        Fields present in the dict are parsed and set. Fields absent from the dict
        keep the CalEvent dataclass default. uid, title, date_start, date_end default
        to None when absent (partial update scenario).
        """
        organizer_raw: dict | None = data.get("organizer")
        conference_raw: dict | None = data.get("conference_data")
        recurrence_raw: dict | None = data.get("recurrence_rule")

        return CalEvent(
            key=data.get("key"),
            calendar_key=data.get("calendar_key"),
            uid=data.get("uid"),
            title=data.get("title"),
            description=data.get("description"),
            location=data.get("location"),
            date_start=self._parse_dt(data["date_start"]) if "date_start" in data else None,
            date_end=self._parse_dt_opt(data.get("date_end")),
            all_day=data.get("all_day", False),
            timezone=data.get("timezone") or "UTC",
            status=self._parse_enum(EventStatus, data.get("status"), EventStatus.CONFIRMED),
            # Left UNDEFINED when the caller omits it so the module can apply the parent calendar's
            # default_type; apply_defaults falls back to PUBLIC when the calendar declares none.
            visibility=self._parse_enum(EventVisibility, data.get("visibility"), EventVisibility.UNDEFINED),
            show_as=self._parse_enum(ShowAs, data.get("show_as"), ShowAs.BUSY),
            color=data.get("color"),
            sequence=data.get("sequence", 0),
            organizer=self._organizer_deserializer.deserialize(organizer_raw) if organizer_raw else None,
            attendees=[self._attendee_deserializer.deserialize(a) for a in data.get("attendees", [])],
            reminders=[self._reminder_deserializer.deserialize(r) for r in data.get("reminders", [])],
            conference_data=self._conference_deserializer.deserialize(conference_raw) if conference_raw else None,
            attachments=[self._attachment_deserializer.deserialize(a) for a in data.get("attachments", [])],
            url=data.get("url"),
            categories=data.get("categories", []),
            related_to=[self._relation_deserializer.deserialize(r) for r in data.get("related_to", [])],
            extra_properties=data.get("extra_properties", {}),
            priority=data.get("priority", 0),
            component_type=self._parse_enum(ComponentType, data.get("component_type"), ComponentType.EVENT),
            percent_complete=data.get("percent_complete"),
            completed_at=self._parse_dt_opt(data.get("completed_at")),
            recurrence_rule=self._recurrence_deserializer.deserialize(recurrence_raw) if recurrence_raw else None,
            recurrence_exceptions=[self._parse_dt(d) for d in data.get("recurrence_exceptions", [])],
            recurrence_id=self._parse_dt_opt(data.get("recurrence_id")),
            recurrence_range=data.get("recurrence_range"),
            uid_parent_split=data.get("uid_parent_split"),
        )

    def deserialize_with_update(self, origin: CalEvent, update: dict | CalEvent) -> CalEvent:
        """Apply an update to an existing CalEvent and return the result.

        When update is a dict, parse each key and apply it to a copy of origin.
        Only keys present in the dict are modified - other fields keep origin's values.
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
            return self._recurrence_deserializer.deserialize(value) if value else None
        if key == "recurrence_exceptions":
            return [self._parse_dt(d) for d in value]
        if key == "date_start":
            return self._parse_dt(value)
        if key in ("date_end", "completed_at", "recurrence_id"):
            return self._parse_dt_opt(value)
        if key == "attendees":
            return [self._attendee_deserializer.deserialize(a) for a in value]
        if key == "reminders":
            return [self._reminder_deserializer.deserialize(r) for r in value]
        if key == "organizer":
            return self._organizer_deserializer.deserialize(value) if value else None
        if key == "conference_data":
            return self._conference_deserializer.deserialize(value) if value else None
        if key == "attachments":
            return [self._attachment_deserializer.deserialize(a) for a in value]
        if key == "related_to":
            return [self._relation_deserializer.deserialize(r) for r in value]
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
        if CalEvent.is_mutable_field(key) or key == "recurrence_range":
            return value
        return _SKIP

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        """Parse an ISO 8601 string into a timezone-aware UTC datetime."""
        return to_utc(datetime.fromisoformat(value))

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
