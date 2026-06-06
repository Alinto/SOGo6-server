from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.api.v1.calendar.schemas.event import DateTimeEndUtcField, DateTimeUtcField
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
    # Full public subscription URL, computed server-side from the share token when active.
    public_url         = fields.String(allow_none=True, dump_only=True)
    # `dump_only`` because permissions are only available when retrieving calendar but can't be set in that way
    permissions        = fields.Dict(allow_none=True, dump_only=True)
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


class CalendarExportQueryArgsSchema(Schema):
    """Query string for the export endpoint."""

    start_date_time = DateTimeUtcField(
        load_default=None, allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime — only return events ending after this instant."},
    )
    end_date_time = DateTimeEndUtcField(
        load_default=None, allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime or date — only return events starting before this instant. Date-only values default to 23:59:59 UTC."},
    )


class CalendarExportDataSchema(Schema):
    """Payload returned when an export is enqueued as an Agent job."""

    job_id = fields.String(required=True, metadata={"description": "Id of the enqueued Agent job. Poll GET /jobs/<job_id> until status is SUCCESS, then fetch GET /jobs/<job_id>/result."})


class CalendarExportResponseSchema(ApiBaseResponse):
    """Response schema for the async export endpoint (returns a job_id, not the ICS)."""

    data = fields.Nested(CalendarExportDataSchema, allow_none=True)


class CalendarImportDataSchema(Schema):
    """Payload returned when an import is enqueued as an Agent job."""

    job_id = fields.String(required=True, metadata={"description": "Id of the enqueued Agent job. Poll GET /jobs/<job_id> until status is SUCCESS; the import counters are then in the job's result {inserted, updated, deleted, total, skipped}."})


class CalendarImportResponseSchema(ApiBaseResponse):
    """Response schema for the async import endpoint (returns a job_id, not the counters)."""

    data = fields.Nested(CalendarImportDataSchema, allow_none=True)


class CalendarSubscriptionDataSchema(Schema):
    """Data returned when a public subscription is enabled."""

    share_token = fields.String()
    public_url  = fields.String()


class CalendarSubscriptionResponseSchema(ApiBaseResponse):
    """Response schema for enabling a public subscription."""

    data = fields.Nested(CalendarSubscriptionDataSchema, allow_none=True)


class CalendarImportUploadSchema(Schema):
    """Multipart file upload schema for the import endpoint.

    Declares the ``file`` part so Swagger renders an upload widget. The actual binary read
    happens in the view since Marshmallow does not deserialize the FileStorage object.
    """

    file = fields.Raw(
        required=True,
        metadata={"type": "string", "format": "binary", "description": "The .ics file to import."},
    )
