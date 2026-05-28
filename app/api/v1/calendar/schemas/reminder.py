from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class ReminderQueryArgsSchema(Schema):
    """Query parameters for listing active reminders."""

    method = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["popup", "email"]),
        metadata={"description": "Filter by reminder method: popup or email."},
    )
    lookahead = fields.Integer(
        load_default=0,
        validate=validate.Range(min=0, max=60),
        metadata={"description": "Extra look-ahead in minutes added after event end (default 0, max 60)."},
    )


class ReminderSchema(Schema):
    """Representation of a single active reminder in API responses."""

    event_key = fields.String()
    title = fields.String(allow_none=True)
    location = fields.String(allow_none=True)
    date_start = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC."})
    date_end = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC."})
    method = fields.String()
    minutes_before = fields.Integer()
    trigger_at = fields.String(metadata={"description": "ISO 8601 UTC datetime when the reminder fires."})
    dates_with_tz = fields.Dict(allow_none=True)


class ReminderListDataSchema(Schema):
    """Data payload for the reminder list response."""

    reminders = fields.List(fields.Nested(ReminderSchema))
    total_count = fields.Integer()


class ReminderListResponseSchema(ApiBaseResponse):
    """Response schema for a list of active reminders."""

    data = fields.Nested(ReminderListDataSchema, allow_none=True)
