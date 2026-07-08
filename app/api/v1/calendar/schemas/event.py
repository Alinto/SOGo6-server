# pylint: disable=wrong-import-order,ungrouped-imports
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from marshmallow import Schema, ValidationError, fields, validate

from app.api.v1.calendar.schemas.components import (
    AttachmentCalendarSchema, AttendeeSchema, ConferenceDataSchema, DatesWithTzSchema, EventRelationSchema,
    OrganizerSchema, RecurrenceRuleSchema, ReminderSchema,
)
from app.module.calendar.CalendarConst import MAX_EVENT_DESCRIPTION_LENGTH, MAX_EVENT_LOCATION_LENGTH, MAX_EVENT_TITLE_LENGTH
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.utils.api.ApiBaseResponse import ApiBaseResponse

_SEARCH_MAX_LENGTH = 200

_EVENT_STATUS_VALUES = EventStatus.event_values()
_VISIBILITY_VALUES = [v.value for v in EventVisibility if v != EventVisibility.UNDEFINED]
_SHOW_AS_VALUES = [s.value for s in ShowAs if s != ShowAs.UNDEFINED]


def _validate_search(value: str | None) -> None:
    if value is not None and len(value.strip()) < 2:
        raise ValidationError("Search query must contain at least 2 non-whitespace characters.")

class DateTimeUtcField(fields.DateTime):
    """DateTime field that always returns a UTC-aware datetime.

    Naive datetimes (no tzinfo) are assumed to be UTC.
    """

    def _deserialize(self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs: Any) -> datetime:
        dt: datetime = super()._deserialize(value, attr, data, **kwargs)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class DateTimeEndUtcField(DateTimeUtcField):
    """DateTime field for an end bound.

    When a date-only string is supplied (no time component), the time is set
    to 23:59:59 so the full day is included in the range.
    """

    def _deserialize(self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs: Any) -> datetime:
        if isinstance(value, str) and "T" not in value and " " not in value:
            value = f"{value}T23:59:59"
        return super()._deserialize(value, attr, data, **kwargs)


class CalendarEventQueryArgsSchema(Schema):
    """
    Query parameters for listing events in a calendar.
    All fields are optional.
    """

    start_date_time = DateTimeUtcField(
        load_default=None,
        allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime - only return events ending after this instant."},
    )
    end_date_time = DateTimeEndUtcField(
        load_default=None,
        allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime or date - only return events starting before this instant. Date-only values default to 23:59:59 UTC."},
    )
    search = fields.String(
        load_default=None,
        allow_none=True,
        validate=[validate.Length(max=_SEARCH_MAX_LENGTH), _validate_search],
        metadata={"description": "Full-text search in title, description and location. Must contain at least 2 non-whitespace characters."},
    )


class CalendarEventSchema(Schema):
    """
    Representation of a single calendar event in API responses.
    Mirrors the CalEvent domain object fields exposed via the REST API.
    """

    key = fields.String(allow_none=True)
    calendar_key = fields.String(allow_none=True)
    uid = fields.String()
    title = fields.String()
    description = fields.String(allow_none=True)
    location = fields.String(allow_none=True)
    date_start = fields.String(metadata={"description": "ISO 8601 UTC with millisecond precision."})
    date_end = fields.String(metadata={"description": "ISO 8601 UTC with millisecond precision."})
    all_day = fields.Boolean()
    timezone = fields.String(allow_none=True)
    status = fields.String(validate=validate.OneOf(_EVENT_STATUS_VALUES))
    visibility = fields.String(validate=validate.OneOf(_VISIBILITY_VALUES))
    show_as = fields.String(validate=validate.OneOf(_SHOW_AS_VALUES))
    url = fields.String(allow_none=True)
    color = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    sequence = fields.Integer()
    organizer = fields.Nested(OrganizerSchema, allow_none=True)
    attendees = fields.List(fields.Nested(AttendeeSchema))
    reminders = fields.List(fields.Nested(ReminderSchema))
    conference_data = fields.Nested(ConferenceDataSchema, allow_none=True)
    related_to = fields.List(fields.Nested(EventRelationSchema))
    attachments = fields.List(fields.Nested(AttachmentCalendarSchema))
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String())
    created_at = fields.String(allow_none=True)
    updated_at = fields.String(allow_none=True)
    component_type = fields.String()
    completed_at = fields.String(allow_none=True)
    recurrence_rule = fields.Nested(RecurrenceRuleSchema, allow_none=True)
    recurrence_exceptions = fields.List(fields.String())
    recurrence_id = fields.String(allow_none=True)
    recurrence_range = fields.String(allow_none=True)
    dates_with_tz = fields.Nested(DatesWithTzSchema, allow_none=True)


class CalendarEventCreateSchema(Schema):
    """Request body for creating a new event."""

    uid = fields.String(load_default=None, allow_none=True)
    title = fields.String(required=True, validate=validate.Length(max=MAX_EVENT_TITLE_LENGTH), metadata={"example": "Team Standup"})
    description = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=MAX_EVENT_DESCRIPTION_LENGTH), metadata={"example": "Daily sync"})
    location = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=MAX_EVENT_LOCATION_LENGTH), metadata={"example": "Conference Room A"})
    date_start = fields.String(required=True,
                               metadata={"description": "ISO 8601 UTC datetime.",
                                         "example": "2026-04-22T09:30:00.000Z"})
    date_end = fields.String(load_default=None, allow_none=True,
                             metadata={"description": "ISO 8601 UTC datetime. Optional for a timed event when the "
                                                      "parent calendar defines default_event_duration_min, which then "
                                                      "derives the end from date_start.",
                                       "example": "2026-04-22T10:00:00.000Z"})
    all_day = fields.Boolean(load_default=False)
    timezone = fields.String(load_default=None, allow_none=True, metadata={"example": "Europe/Paris"})
    status = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(_EVENT_STATUS_VALUES),
                           metadata={"example": "confirmed"})
    visibility = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(_VISIBILITY_VALUES),
                               metadata={"example": "public"})
    show_as = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(_SHOW_AS_VALUES),
                            metadata={"example": "busy"})
    url = fields.String(load_default=None, allow_none=True)
    color = fields.String(load_default=None, allow_none=True, metadata={"example": "#3B82F6"})
    categories = fields.List(fields.String(), load_default=list, metadata={"example": []})
    sequence = fields.Integer(load_default=0)
    organizer = fields.Nested(OrganizerSchema, load_default=None, allow_none=True, metadata={"example": None})
    attendees = fields.List(fields.Nested(AttendeeSchema), load_default=list, metadata={"example": []})
    reminders = fields.List(fields.Nested(ReminderSchema), load_default=list, metadata={"example": []})
    conference_data = fields.Nested(ConferenceDataSchema, load_default=None, allow_none=True, metadata={"example": None})
    related_to = fields.List(fields.Nested(EventRelationSchema), load_default=list, metadata={"example": []})
    attachments = fields.List(fields.Nested(AttachmentCalendarSchema), load_default=list, metadata={"example": []})
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String(), load_default=dict, metadata={"example": {}})
    recurrence_rule = fields.Nested(RecurrenceRuleSchema, load_default=None, allow_none=True, metadata={"example": None})
    recurrence_exceptions = fields.List(fields.String(), load_default=list, metadata={"example": []})
    recurrence_id = fields.String(load_default=None, allow_none=True)
    completed_at = fields.String(load_default=None, allow_none=True)


class CalendarEventPatchSchema(Schema):
    """Request body for partially updating an event. All fields are optional."""

    title = fields.String(validate=validate.Length(max=MAX_EVENT_TITLE_LENGTH))
    description = fields.String(allow_none=True, validate=validate.Length(max=MAX_EVENT_DESCRIPTION_LENGTH))
    location = fields.String(allow_none=True, validate=validate.Length(max=MAX_EVENT_LOCATION_LENGTH))
    date_start = fields.String(metadata={"description": "ISO 8601 UTC datetime."})
    date_end = fields.String(metadata={"description": "ISO 8601 UTC datetime."})
    all_day = fields.Boolean()
    timezone = fields.String(allow_none=True)
    status = fields.String(allow_none=True, validate=validate.OneOf(_EVENT_STATUS_VALUES))
    visibility = fields.String(allow_none=True, validate=validate.OneOf(_VISIBILITY_VALUES))
    show_as = fields.String(allow_none=True, validate=validate.OneOf(_SHOW_AS_VALUES))
    url = fields.String(allow_none=True)
    color = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    sequence = fields.Integer()
    organizer = fields.Nested(OrganizerSchema, allow_none=True)
    attendees = fields.List(fields.Nested(AttendeeSchema))
    reminders = fields.List(fields.Nested(ReminderSchema))
    conference_data = fields.Nested(ConferenceDataSchema, allow_none=True)
    related_to = fields.List(fields.Nested(EventRelationSchema))
    attachments = fields.List(fields.Nested(AttachmentCalendarSchema))
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String())
    recurrence_rule = fields.Nested(RecurrenceRuleSchema, allow_none=True)
    recurrence_exceptions = fields.List(fields.String())
    recurrence_id = fields.String(allow_none=True)
    recurrence_range = fields.String(allow_none=True)
    completed_at = fields.String(allow_none=True)


class AttendanceSchema(Schema):
    """Request body for updating the current user's attendance status for an event."""

    status = fields.String(
        required=True,
        validate=validate.OneOf(["accepted", "declined", "tentative", "delegated"]),
        metadata={"description": "accepted | declined | tentative | delegated"},
    )
    recurrence_id = DateTimeUtcField(
        load_default=None, allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime. When set, the status applies to this single occurrence only."},
    )


class CalendarEventResponseSchema(ApiBaseResponse):
    """Response schema for a single calendar event."""

    data = fields.Nested(CalendarEventSchema, allow_none=True)


class CalendarEventListDataSchema(Schema):
    """Data payload for the event list response."""

    events = fields.List(fields.Nested(CalendarEventSchema))
    total_count = fields.Integer()


class CalendarEventListResponseSchema(ApiBaseResponse):
    """Response schema for a list of calendar events."""

    data = fields.Nested(CalendarEventListDataSchema, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Return an example response for OpenAPI documentation."""
        return {
            "data": {
                "events": [
                    {
                        "key": "550e8400-e29b-41d4-a716-446655440000",
                        "calendar_key": "7f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                        "uid": "evt_001@sogo.example.com",
                        "title": "Team Standup",
                        "description": "Daily team sync meeting",
                        "location": "Conference Room A",
                        "date_start": "2026-03-19T09:30:00.000Z",
                        "date_end": "2026-03-19T10:00:00.000Z",
                        "all_day": False,
                        "timezone": "Europe/Paris",
                        "status": "confirmed",
                        "visibility": "public",
                        "show_as": "busy",
                        "color": None,
                        "sequence": 0,
                        "organizer": None,
                        "attendees": [],
                        "reminders": [],
                        "conference_data": None,
                        "attachments": [],
                        "created_at": None,
                        "updated_at": None,
                    }
                ],
                "total_count": 1,
            },
            "error_code": "S000000",
            "error_msg": "No Error",
        }
