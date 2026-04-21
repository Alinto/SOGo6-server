from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.serializer.CalendarEventSerializer import CalendarEventSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventSerializerJson(CalendarEventSerializer):
    """
    Serializes calendar events to JSON format matching the SOGo6 REST API schema.
    Datetimes are formatted as ISO 8601 UTC with millisecond precision (e.g. 2026-03-19T09:30:00.000Z).
    Enum values are serialized as their lowercase string representation.
    None values and empty lists are included as null / [] for predictable API responses.
    """

    def serialize(self, event: CalEvent) -> str:
        """Serialize a CalEvent to a JSON string."""
        return json.dumps(self.to_dict(event), ensure_ascii=False)

    def to_dict(self, event: CalEvent) -> dict[str, Any]:
        """Convert a CalEvent to a plain dict matching the REST API schema."""
        return {
            "uid": event.uid,
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "date_start": self._fmt_dt(event.date_start),
            "date_end": self._fmt_dt(event.date_end),
            "all_day": event.all_day,
            "timezone": event.timezone,
            "status": event.status.value,
            "visibility": event.visibility.value,
            "show_as": event.show_as.value,
            "color": event.color,
            "sequence": event.sequence,
            "organizer": self._organizer_to_dict(event.organizer) if event.organizer else None,
            "attendees": [self._attendee_to_dict(a) for a in event.attendees],
            "reminders": [self._reminder_to_dict(r) for r in event.reminders],
            "conference_data": self._conference_to_dict(event.conference_data) if event.conference_data else None,
            "url": event.url,
            "categories": event.categories,
            "related_to": [self._relation_to_dict(r) for r in event.related_to],
            "extra_properties": event.extra_properties,
            "attachments": [self._attachment_to_dict(a) for a in event.attachments],
            "created_at": self._fmt_dt(event.created_at) if event.created_at else None,
            "updated_at": self._fmt_dt(event.updated_at) if event.updated_at else None,
            "component_type": event.component_type.value,
            "percent_complete": event.percent_complete,
            "completed_at": self._fmt_dt(event.completed_at) if event.completed_at else None,
        }

    # ------------------------------------------------------------------
    # Sub-object converters
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Datetime formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_dt(dt: datetime) -> str:
        """Format a datetime as ISO 8601 UTC with millisecond precision ending in Z."""
        ms = dt.microsecond // 1000
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"
