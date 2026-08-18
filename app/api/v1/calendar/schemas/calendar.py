from __future__ import annotations

from typing import Any
from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.api.v1.calendar.schemas.components import CalendarPermissionsSchema
from app.api.v1.calendar.schemas.event import DateTimeEndUtcField, DateTimeUtcField
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.utils.api.ApiBaseResponse import ApiBaseResponse

_COLOR_REGEX = r"^#[0-9A-Fa-f]{6}$"
# RFC 5545 CLASS values exposed to the API (UNDEFINED is internal-only).
_VISIBILITY_VALUES = [v.value for v in EventVisibility if v != EventVisibility.UNDEFINED]


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
    include_in_freebusy        = fields.Boolean(load_default=True,
                                metadata={"description": "When false, this calendar's events are excluded from the owner's free/busy."})
    default_event_duration_min = fields.Integer(load_default=None, allow_none=True,
                                metadata={"description": "Default duration applied to a new event left without an explicit end."})
    default_alarm_duration_min = fields.Integer(load_default=None, allow_none=True,
                                metadata={"description": "Default offset for an alarm added without an explicit one."})
    default_type               = fields.String(load_default=None, allow_none=True,
                                validate=validate.OneOf(_VISIBILITY_VALUES),
                                metadata={"description": "Default visibility (RFC 5545 CLASS) for new events."})


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
    include_in_freebusy        = fields.Boolean()
    default_event_duration_min = fields.Integer(allow_none=True)
    default_alarm_duration_min = fields.Integer(allow_none=True)
    default_type               = fields.String(allow_none=True, validate=validate.OneOf(_VISIBILITY_VALUES))


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
    include_in_freebusy        = fields.Boolean()
    default_event_duration_min = fields.Integer(allow_none=True)
    default_alarm_duration_min = fields.Integer(allow_none=True)
    default_type               = fields.String(allow_none=True)
    # Full public subscription URL, computed server-side from the share token when active.
    public_url         = fields.String(allow_none=True, dump_only=True)
    # `dump_only`` because permissions are only available when retrieving calendar but can't be set in that way
    permissions        = fields.Nested(CalendarPermissionsSchema, allow_none=True, dump_only=True)
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
        metadata={"description": "ISO 8601 UTC datetime - only return events ending after this instant."},
    )
    end_date_time = DateTimeEndUtcField(
        load_default=None, allow_none=True,
        metadata={"description": "ISO 8601 UTC datetime or date - only return events starting before this instant. Date-only values default to 23:59:59 UTC."},
    )


class CalendarExportDataSchema(Schema):
    """Payload returned when an export is enqueued as an Agent job."""

    job_id = fields.String(required=True, metadata={"description": "Id of the enqueued Agent job. Poll GET /jobs/<job_id> until status is SUCCESS, then fetch GET /jobs/<job_id>/result."})


class CalendarExportResponseSchema(ApiBaseResponse):
    """Response schema for the async export endpoint (returns a job_id, not the ICS)."""

    data = fields.Nested(CalendarExportDataSchema, allow_none=True)


class CalendarImportDataSchema(Schema):
    """Payload returned when an import is enqueued as an Agent job."""

    inserted = fields.Integer(required=False, allow_none=True, metadata={"description": "Number of events inserted (sync only)."})
    updated = fields.Integer(required=False, allow_none=True, metadata={"description": "Number of events updated (sync only)."})
    deleted = fields.Integer(required=False, allow_none=True, metadata={"description": "Number of events deleted (sync only)."})
    total = fields.Integer(required=False, allow_none=True, metadata={"description": "Total number of events processed (sync only)."})
    skipped = fields.Integer(required=False, allow_none=True, metadata={"description": "Number of events skipped (sync only)."})


class CalendarImportResponseSchema(ApiBaseResponse):
    """Response schema for the import endpoint (handles both async and sync modes)."""

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


class CalendarShareRightsSchema(Schema):
    """Permission rights for different event visibility levels."""

    public = fields.String(
        required=True,
        validate=validate.OneOf(["view-all", "view-date-time", "respond-to", "modify", "none"]),
        metadata={"description": "Permission for public events: view-all | view-date-time | respond-to | modify | none", "example": "view-all"}
    )
    confidential = fields.String(
        required=True,
        validate=validate.OneOf(["view-all", "view-date-time", "respond-to", "modify", "none"]),
        metadata={"description": "Permission for confidential events: view-all | view-date-time | respond-to | modify | none", "example": "view-date-time"}
    )
    private = fields.String(
        required=True,
        validate=validate.OneOf(["view-all", "view-date-time", "respond-to", "modify", "none"]),
        metadata={"description": "Permission for private events: view-all | view-date-time | respond-to | modify | none", "example": "none"}
    )
    can_create_objects = fields.Boolean(required=True, metadata={"description": "Can create new events", "example": True})
    can_erase_objects = fields.Boolean(required=True, metadata={"description": "Can delete events", "example": False})


class CalendarShareUserSchema(Schema):
    """User permission entry in calendar sharing.

    ``c_email`` and ``uid`` are required unless ``user_class`` is ``"anyone"``, in which case
    they are ignored (the share applies to any authenticated user, not a specific one).
    """

    c_email = fields.String(required=False, allow_none=True, metadata={"description": "User email address", "example": "jdoe@example.org"})
    uid = fields.String(required=False, allow_none=True, metadata={"description": "User UID", "example": "jdoe"})
    user_class = fields.String(
        required=True,
        validate=validate.OneOf(["user", "anyone"]),
    )
    rights = fields.Nested(CalendarShareRightsSchema, required=True, metadata={"description": "Permission rights for this user"})

    @validates_schema
    def validate_user_identity(self, data: dict[str, Any], **kwargs: Any) -> None:  # pylint: disable=unused-argument
        """Require c_email and uid unless user_class is 'anyone'."""
        if data.get("user_class") == "anyone":
            return
        errors: dict[str, list[str]] = {}
        if not data.get("c_email"):
            errors["c_email"] = ["Missing data for required field."]
        if not data.get("uid"):
            errors["uid"] = ["Missing data for required field."]
        if errors:
            raise ValidationError(errors)

class CalendarSharePatchSchema(CalendarShareUserSchema):
    """Request body item for PATCH /calendars/{key}/share - partial update of user permissions.

    The endpoint expects a JSON list of these objects (use with ``many=True``).
    Only the users specified in the request are modified. Other existing permissions remain unchanged.
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "jdoe@example.org",
                "uid": "jdoe",
                "user_class": "user",
                "rights": {
                    "public": "view-all",
                    "confidential": "view-date-time",
                    "private": "none",
                    "can_create_objects": True,
                    "can_erase_objects": False
                }
            }
        ]


class CalendarSharePutSchema(CalendarShareUserSchema):
    """Request body item for PUT /calendars/{key}/share - replace all user permissions.

    The endpoint expects a JSON list of these objects (use with ``many=True``).
    All existing permissions are replaced by the users specified in the request.
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "jdoe@example.org",
                "uid": "jdoe",
                "user_class": "user",
                "rights": {
                    "public": "view-all",
                    "confidential": "view-date-time",
                    "private": "none",
                    "can_create_objects": True,
                    "can_erase_objects": False
                }
            },
            {
                "c_email": "alice@example.org",
                "uid": "alice",
                "user_class": "user",
                "rights": {
                    "public": "modify",
                    "confidential": "modify",
                    "private": "view-date-time",
                    "can_create_objects": True,
                    "can_erase_objects": True
                }
            }
        ]


class CalendarSharePostSchema(CalendarShareUserSchema):
    """Request body item for POST /calendars/{key}/share - grant full modify permissions to users.

    The endpoint expects a JSON list of these objects (use with ``many=True``).
    Grants 'modify' permission for all event types and object management rights to the specified users.
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "jdoe@example.org",
                "uid": "jdoe",
                "user_class": "user",
                "rights": {
                    "public": "modify",
                    "confidential": "modify",
                    "private": "modify",
                    "can_create_objects": True,
                    "can_erase_objects": True
                }
            }
        ]


class CalendarShareResponseSchema(ApiBaseResponse):
    """Response schema for calendar sharing endpoints. ``data`` is a plain list of users."""

    data = fields.List(fields.Nested(CalendarShareUserSchema), allow_none=True)

    @staticmethod
    def example() -> dict[str, Any]:
        """Example full envelope for Swagger documentation."""
        return {
            "data": [
                {
                    "c_email": "jdoe@example.org",
                    "uid": "jdoe",
                    "user_class": "user",
                    "rights": {
                        "public": "view-all",
                        "confidential": "view-date-time",
                        "private": "none",
                        "can_create_objects": True,
                        "can_erase_objects": False
                    }
                }
            ],
            "error_code": "S000000",
            "error_msg": "No Error"
        }
