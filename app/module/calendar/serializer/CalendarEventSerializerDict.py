from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.serializer.CalendarEventSerializer import CalendarEventSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventSerializerDict(CalendarEventSerializer[dict]):
    """
    Converts CalEvent objects to plain dicts matching the SOGo6 REST API schema.
    Datetimes are formatted as ISO 8601 UTC with millisecond precision (e.g. 2026-03-19T09:30:00.000Z).
    Enum values are serialized as their lowercase string representation.
    None values and empty lists are included as null / [] for predictable API responses.
    """

    def serialize(self, data: CalEvent) -> dict[str, Any]:
        """Convert a CalEvent to a plain dict matching the REST API schema."""
        return {
            "key": data.key,
            "calendar_key": data.calendar_key,
            "uid": data.uid,
            "title": data.title,
            "description": data.description,
            "location": data.location,
            "date_start": self._fmt_dt(data.date_start),
            "date_end": self._fmt_dt(data.date_end),
            "all_day": data.all_day,
            "timezone": data.timezone,
            "status": data.status.value,
            "visibility": data.visibility.value,
            "show_as": data.show_as.value,
            "color": data.color,
            "sequence": data.sequence,
            "priority": data.priority,
            "organizer": self._organizer_to_dict(data.organizer) if data.organizer else None,
            "attendees": [self._attendee_to_dict(a) for a in data.attendees],
            "reminders": [self._reminder_to_dict(r) for r in data.reminders],
            "conference_data": self._conference_to_dict(data.conference_data) if data.conference_data else None,
            "url": data.url,
            "categories": data.categories,
            "related_to": [self._relation_to_dict(r) for r in data.related_to],
            "extra_properties": data.extra_properties,
            "attachments": [self._attachment_to_dict(a) for a in data.attachments],
            "created_at": self._fmt_dt(data.created_at) if data.created_at else None,
            "updated_at": self._fmt_dt(data.updated_at) if data.updated_at else None,
            "component_type": data.component_type.value,
            "percent_complete": data.percent_complete,
            "completed_at": self._fmt_dt(data.completed_at) if data.completed_at else None,
            "recurrence_rule": self._recurrence_rule_to_dict(data.recurrence_rule) if data.recurrence_rule else None,
            "recurrence_exceptions": [self._fmt_dt(d) for d in data.recurrence_exceptions],
            "recurrence_id": self._fmt_dt(data.recurrence_id) if data.recurrence_id else None,
            "recurrence_range": data.recurrence_range,
            "dates_with_tz": self._dates_with_tz(data),
        }

    @staticmethod
    def _organizer_to_dict(org: CalOrganizer) -> dict[str, Any]:
        return {
            "email": org.email,
            "name": org.name,
            "role": org.role.value if org.role else None,
            "status": org.status.value if org.status else None,
            "sent_by": org.sent_by,
            "dir_ref": org.dir_ref,
        }

    @staticmethod
    def _attendee_to_dict(att: CalAttendee) -> dict[str, Any]:
        return {
            "email": att.email,
            "name": att.name,
            "role": att.role.value,
            "status": att.status.value,
            "rsvp": att.rsvp,
            "cutype": att.cutype.value,
            "delegated_from": att.delegated_from,
            "delegated_to": att.delegated_to,
            "sent_by": att.sent_by,
            "dir_ref": att.dir_ref,
        }

    @staticmethod
    def _relation_to_dict(rel: CalEventRelation) -> dict[str, Any]:
        return {
            "uid": rel.uid,
            "relation_type": rel.relation_type.value,
        }

    @staticmethod
    def _reminder_to_dict(rem: CalReminder) -> dict[str, Any]:
        return {
            "method": rem.method.value,
            "minutes_before": rem.minutes_before,
        }

    @staticmethod
    def _attachment_to_dict(att: CalAttachment) -> dict[str, Any]:
        return {
            "filename": att.filename,
            "mime_type": att.mime_type,
            "url": att.url,
            "size": att.size,
        }

    @staticmethod
    def _conference_to_dict(cd: CalConferenceData) -> dict[str, Any]:
        return {
            "type": cd.type,
            "url": cd.url,
            "conference_id": cd.conference_id,
            "entry_points": [
                {"type": ep.type, "uri": ep.uri, "label": ep.label}
                for ep in cd.entry_points
            ],
        }

    @staticmethod
    def _recurrence_rule_to_dict(rule: CalRecurrenceRule) -> dict[str, Any]:
        return {
            "frequency": rule.frequency.value,
            "interval": rule.interval,
            "until": CalendarEventSerializerDict._fmt_dt(rule.until) if rule.until else None,
            "count": rule.count,
            "by_day": rule.by_day,
            "by_month_day": rule.by_month_day,
            "by_month": rule.by_month,
            "by_year_day": rule.by_year_day,
            "by_week_no": rule.by_week_no,
            "by_set_pos": rule.by_set_pos,
            "by_hour": rule.by_hour,
            "by_minute": rule.by_minute,
            "by_second": rule.by_second,
            "week_start": rule.week_start,
        }

    def _dates_with_tz(self, event: CalEvent) -> dict[str, str | None]:  # type: ignore[override]
        """Build the dates_with_tz dict for the event and calendar timezones."""
        event_tz = event.timezone or None
        cal_tz = event.calendar_timezone or None
        return {
            "date_start_tz_event": self._apply_tz(event.date_start, event_tz) if event_tz else None,
            "date_end_tz_event": self._apply_tz(event.date_end, event_tz) if event_tz else None,
            "date_start_tz_calendar": self._apply_tz(event.date_start, cal_tz) if cal_tz else None,
            "date_end_tz_calendar": self._apply_tz(event.date_end, cal_tz) if cal_tz else None,
        }

    @staticmethod
    def _fmt_dt(dt: datetime) -> str:
        """Format a datetime as ISO 8601 UTC with millisecond precision ending in Z.

        Naive datetimes are assumed UTC. Non-UTC datetimes are converted to UTC first.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elif dt.tzinfo != timezone.utc:
            dt = dt.astimezone(timezone.utc)
        ms = dt.microsecond // 1000
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

    @staticmethod
    def _apply_tz(dt: datetime, tz_name: str) -> str | None:
        """Convert dt to the given IANA timezone and return an ISO 8601 string with UTC offset."""
        try:
            return dt.astimezone(ZoneInfo(tz_name)).isoformat()
        except (ZoneInfoNotFoundError, KeyError):
            return None
