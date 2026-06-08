from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse
from app.api.v1.calendar.schemas.calendar import CalendarSchema
from app.api.v1.calendar.schemas.components import SyncConfigUpdateSchema, SyncResultSchema


class ExternalCalendarCreateSchema(Schema):
    """Request body for creating an external ICS calendar subscription."""

    name = fields.String(required=True, metadata={"example": "Team Calendar"})
    url = fields.Url(required=True, metadata={"example": "https://example.com/calendar.ics"})
    color = fields.String(load_default=None, allow_none=True, metadata={"example": "#3B82F6"})
    sync_interval_minutes = fields.Integer(
        load_default=60,
        validate=validate.Range(min=5, max=1440),
        metadata={"description": "Sync interval in minutes (default 60, min 5, max 1440)."},
    )


class ExternalCalendarUpdateSchema(Schema):
    """Request body for updating an external ICS calendar."""

    name = fields.String()
    color = fields.String(allow_none=True)
    sync_config = fields.Nested(SyncConfigUpdateSchema, metadata={"description": "Partial sync_config update (url, sync_interval_minutes)."})


class ExternalCalendarListDataSchema(Schema):
    """Data payload for the external calendar list response."""

    calendars = fields.List(fields.Nested(CalendarSchema))
    total_count = fields.Integer()


class ExternalCalendarListResponseSchema(ApiBaseResponse):
    """Response schema for a list of external calendars."""

    data = fields.Nested(ExternalCalendarListDataSchema, allow_none=True)


class ExternalCalendarResponseSchema(ApiBaseResponse):
    """Response schema for a single external calendar."""

    data = fields.Nested(CalendarSchema, allow_none=True)


class SyncStatusSchema(Schema):
    """Response data for sync status."""

    sync_status = fields.String()
    last_sync = fields.String(allow_none=True)
    sync_error = fields.String(allow_none=True)


class SyncStatusResponseSchema(ApiBaseResponse):
    """Response schema for sync status."""

    data = fields.Nested(SyncStatusSchema, allow_none=True)


class SyncTriggerResponseSchema(ApiBaseResponse):
    """Response schema for triggering a sync."""

    data = fields.Nested(SyncResultSchema, allow_none=True)
