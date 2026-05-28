from __future__ import annotations

from marshmallow import Schema, fields

from app.api.v1.calendar.schemas.event import DateTimeEndUtcField, DateTimeUtcField
from app.utils.api.ApiBaseResponse import ApiBaseResponse


class FreeBusyRequestSchema(Schema):
    """Request body for a free/busy JSON query."""

    target_uids = fields.List(
        fields.String(),
        required=True,
        metadata={"example": ["user1@example.com", "user2@example.com"]},
    )
    start = DateTimeUtcField(
        required=True,
        metadata={"example": "2026-04-22T00:00:00Z"},
    )
    end = DateTimeEndUtcField(
        required=True,
        metadata={"example": "2026-04-22T23:59:59Z"},
    )


class FreeBusyPeriodSchema(Schema):
    """A single free/busy period."""

    start = fields.String()
    end   = fields.String()
    type  = fields.String()
    title = fields.String(load_default=None, allow_none=True)


class FreeBusyAttendeeSchema(Schema):
    """Free/busy data for a single attendee."""

    periods = fields.List(fields.Nested(FreeBusyPeriodSchema))


class FreeBusyDataSchema(Schema):
    """Free/busy response payload."""

    start            = fields.String()
    end              = fields.String()
    attendees        = fields.Dict(keys=fields.String(), values=fields.Nested(FreeBusyAttendeeSchema))
    is_available     = fields.Boolean(load_default=None, allow_none=True)


class FreeBusyResponseSchema(ApiBaseResponse):
    """API response wrapper for a free/busy JSON response."""

    data = fields.Nested(FreeBusyDataSchema, allow_none=True)
