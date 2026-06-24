from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.module.calendar.serializer.CalAttachmentSerializerDict import CalAttachmentSerializerDict
from app.module.calendar.serializer.CalAttendeeSerializerDict import CalAttendeeSerializerDict
from app.module.calendar.serializer.CalConferenceDataSerializerDict import CalConferenceDataSerializerDict
from app.module.calendar.serializer.CalEventRelationSerializerDict import CalEventRelationSerializerDict
from app.module.calendar.serializer.CalEventSerializer import CalEventSerializer
from app.module.calendar.serializer.CalOrganizerSerializerDict import CalOrganizerSerializerDict
from app.module.calendar.serializer.CalRecurrenceRuleSerializerDict import CalRecurrenceRuleSerializerDict
from app.module.calendar.serializer.CalReminderSerializerDict import CalReminderSerializerDict
from app.utils.datetime.DateTimeUtils import apply_tz, fmt_dt

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalEventSerializerDict(CalEventSerializer[dict]):
    """
    Converts CalEvent objects to plain dicts matching the SOGo6 REST API schema.
    Datetimes are formatted as ISO 8601 UTC with millisecond precision (e.g. 2026-03-19T09:30:00.000Z).
    Enum values are serialized as their lowercase string representation.
    None values and empty lists are included as null / [] for predictable API responses.
    Multi-valued sub-objects are delegated to their own serializers.
    """

    def __init__(self) -> None:
        self._organizer_serializer = CalOrganizerSerializerDict()
        self._attendee_serializer = CalAttendeeSerializerDict()
        self._reminder_serializer = CalReminderSerializerDict()
        self._conference_serializer = CalConferenceDataSerializerDict()
        self._relation_serializer = CalEventRelationSerializerDict()
        self._attachment_serializer = CalAttachmentSerializerDict()
        self._recurrence_rule_serializer = CalRecurrenceRuleSerializerDict()

    def serialize(self, data: CalEvent) -> dict[str, Any]:
        """Convert a CalEvent to a plain dict matching the REST API schema."""
        return {
            "key": data.key,
            "calendar_key": data.calendar_key,
            "uid": data.uid,
            "title": data.title,
            "description": data.description,
            "location": data.location,
            "date_start": fmt_dt(data.require_date_start),
            "date_end": fmt_dt(data.date_end) if data.date_end is not None else None,
            "all_day": data.all_day,
            "timezone": data.timezone,
            "status": data.status.value,
            "visibility": data.visibility.value,
            "show_as": data.show_as.value,
            "color": data.color,
            "sequence": data.sequence,
            "priority": data.priority,
            "organizer": self._organizer_serializer.serialize(data.organizer) if data.organizer else None,
            "attendees": [self._attendee_serializer.serialize(a) for a in data.attendees],
            "reminders": [self._reminder_serializer.serialize(r) for r in data.reminders],
            "conference_data": self._conference_serializer.serialize(data.conference_data) if data.conference_data else None,
            "url": data.url,
            "categories": data.categories,
            "related_to": [self._relation_serializer.serialize(r) for r in data.related_to],
            "extra_properties": data.extra_properties,
            "attachments": [self._attachment_serializer.serialize(a) for a in data.attachments],
            "created_at": fmt_dt(data.created_at) if data.created_at else None,
            "updated_at": fmt_dt(data.updated_at) if data.updated_at else None,
            "component_type": data.component_type.value,
            "percent_complete": data.percent_complete,
            "completed_at": fmt_dt(data.completed_at) if data.completed_at else None,
            "recurrence_rule": self._recurrence_rule_serializer.serialize(data.recurrence_rule) if data.recurrence_rule else None,
            "recurrence_exceptions": [fmt_dt(d) for d in data.recurrence_exceptions],
            "recurrence_id": fmt_dt(data.recurrence_id) if data.recurrence_id else None,
            "recurrence_range": data.recurrence_range,
            "uid_parent_split": data.uid_parent_split,
            "dates_with_tz": self._dates_with_tz(data),
        }

    def _dates_with_tz(self, event: CalEvent) -> dict[str, str | None]:  # type: ignore[override]
        """Build the dates_with_tz dict for the event and calendar timezones."""
        event_tz = event.timezone
        cal_tz = event.calendar_timezone
        return {
            "date_start_tz_event": apply_tz(event.require_date_start, event_tz) if event_tz else None,
            "date_end_tz_event": apply_tz(event.date_end, event_tz) if (event_tz and event.date_end is not None) else None,
            "date_start_tz_calendar": apply_tz(event.require_date_start, cal_tz) if cal_tz else None,
            "date_end_tz_calendar": apply_tz(event.date_end, cal_tz) if (cal_tz and event.date_end is not None) else None,
        }
