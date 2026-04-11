# pylint: disable=wrong-import-order,ungrouped-imports
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse

_SEARCH_MAX_LENGTH = 200

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
        metadata={"description": "ISO 8601 UTC datetime — only return events ending after this instant."},
    )
    end_date_time = DateTimeEndUtcField(
        load_default=None,
        allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime or date — only return events starting before this instant. Date-only values default to 23:59:59 UTC."},
    )
    search = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=_SEARCH_MAX_LENGTH),
        metadata={"description": "Full-text search in title, description and location."},
    )


class CalendarEventSchema(Schema):
    """
    Representation of a single calendar event in API responses.
    Mirrors the CalEvent domain object fields exposed via the REST API.
    """

    id = fields.String(allow_none=True)
    calendar_id = fields.String(allow_none=True)
    uid = fields.String()
    title = fields.String()
    description = fields.String(allow_none=True)
    location = fields.String(allow_none=True)
    start_date = fields.String(metadata={"description": "ISO 8601 UTC with millisecond precision."})
    end_date = fields.String(metadata={"description": "ISO 8601 UTC with millisecond precision."})
    all_day = fields.Boolean()
    timezone = fields.String()
    status = fields.String()
    visibility = fields.String()
    show_as = fields.String()
    url = fields.String(allow_none=True)
    color = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    sequence = fields.Integer()
    organizer = fields.Dict(allow_none=True)
    attendees = fields.List(fields.Dict())
    reminders = fields.List(fields.Dict())
    conference_data = fields.Dict(allow_none=True)
    related_to = fields.List(fields.Dict())
    attachments = fields.List(fields.Dict())
    created_at = fields.String(allow_none=True)
    updated_at = fields.String(allow_none=True)


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
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "calendar_id": "7f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                        "uid": "evt_001@sogo.example.com",
                        "title": "Team Standup",
                        "description": "Daily team sync meeting",
                        "location": "Conference Room A",
                        "start_date": "2026-03-19T09:30:00.000Z",
                        "end_date": "2026-03-19T10:00:00.000Z",
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
