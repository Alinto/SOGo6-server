from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse

_COLOR_REGEX = r"^#[0-9A-Fa-f]{6}$"


class CalendarCreateSchema(Schema):
    """Request body for creating a calendar."""

    name        = fields.String(required=True, validate=validate.Length(min=1, max=255),
                                metadata={"example": "Work"})
    color       = fields.String(load_default="#3B82F6", validate=validate.Regexp(_COLOR_REGEX),
                                metadata={"example": "#3B82F6"})
    description = fields.String(load_default=None, allow_none=True,
                                metadata={"example": "Professional calendar"})
    timezone    = fields.String(load_default="UTC", validate=validate.Length(max=64),
                                metadata={"example": "Europe/Paris"})


class CalendarUpdateSchema(Schema):
    """Request body for updating a calendar (all fields optional)."""

    name        = fields.String(validate=validate.Length(min=1, max=255),
                                metadata={"example": "Work"})
    color       = fields.String(validate=validate.Regexp(_COLOR_REGEX),
                                metadata={"example": "#3B82F6"})
    description = fields.String(allow_none=True,
                                metadata={"example": "Professional calendar"})
    timezone    = fields.String(validate=validate.Length(max=64),
                                metadata={"example": "Europe/Paris"})
    is_default  = fields.Boolean()


class CalendarSchema(Schema):
    """Representation of a calendar in API responses."""

    key                = fields.String()
    name               = fields.String()
    color              = fields.String(allow_none=True)
    description        = fields.String(allow_none=True)
    timezone           = fields.String()
    is_default         = fields.Boolean()
    source_type        = fields.String()
    ctag               = fields.Integer()
    share_token = fields.String(allow_none=True)
    created_at         = fields.DateTime(allow_none=True)
    updated_at         = fields.DateTime(allow_none=True)


class CalendarListDataSchema(Schema):
    """Data payload for the calendar list response."""

    calendars   = fields.List(fields.Nested(CalendarSchema))
    total_count = fields.Integer()


class CalendarListResponseSchema(ApiBaseResponse):
    """Response schema for a list of calendars."""

    data = fields.Nested(CalendarListDataSchema, allow_none=True)


class CalendarResponseSchema(ApiBaseResponse):
    """Response schema for a single calendar."""

    data = fields.Nested(CalendarSchema, allow_none=True)
