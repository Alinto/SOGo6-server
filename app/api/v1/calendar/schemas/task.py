from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse
from .event import CalendarEventQueryArgsSchema  # reuse date range / search args

_SEARCH_MAX_LENGTH = 200


class CalendarTaskQueryArgsSchema(CalendarEventQueryArgsSchema):
    """Query parameters for listing tasks (same date range / search as events)."""


class CalendarTaskSchema(Schema):
    """Representation of a single VTODO in API responses."""

    id = fields.String(allow_none=True)
    calendar_key = fields.String(allow_none=True)
    uid = fields.String()
    title = fields.String()
    description = fields.String(allow_none=True)
    date_start = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC start (optional for VTODOs)."})
    due = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC due date (maps to RFC 5545 DUE)."})
    status = fields.String()
    visibility = fields.String()
    priority = fields.Integer()
    percent_complete = fields.Integer(allow_none=True)
    completed_at = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    reminders = fields.List(fields.Dict())
    organizer = fields.Dict(allow_none=True)
    attendees = fields.List(fields.Dict())
    related_to = fields.List(fields.Dict())
    attachments = fields.List(fields.Dict())
    extra_properties = fields.Dict()
    recurrence_rule = fields.Dict(allow_none=True)
    recurrence_exceptions = fields.List(fields.String())
    component_type = fields.String()
    created_at = fields.String(allow_none=True)
    updated_at = fields.String(allow_none=True)


class CalendarTaskCreateSchema(Schema):
    """Request body for creating a new VTODO."""

    uid = fields.String(load_default=None, allow_none=True)
    title = fields.String(required=True)
    description = fields.String(load_default=None, allow_none=True)
    date_start = fields.String(load_default=None, allow_none=True,
                               metadata={"description": "ISO 8601 UTC. Defaults to now if absent."})
    due = fields.String(load_default=None, allow_none=True,
                        metadata={"description": "ISO 8601 UTC due date (RFC 5545 DUE). No limit if absent."})
    status = fields.String(load_default=None, allow_none=True,
                           metadata={"description": "needs_action | in_process | completed | cancelled"})
    visibility = fields.String(load_default=None, allow_none=True)
    priority = fields.Integer(load_default=0, validate=validate.Range(min=0, max=9))
    percent_complete = fields.Integer(load_default=None, allow_none=True,
                                      validate=validate.Range(min=0, max=100))
    completed_at = fields.String(load_default=None, allow_none=True)
    categories = fields.List(fields.String(), load_default=list)
    reminders = fields.List(fields.Dict(), load_default=list)
    organizer = fields.Dict(load_default=None, allow_none=True)
    attendees = fields.List(fields.Dict(), load_default=list)
    related_to = fields.List(fields.Dict(), load_default=list)
    attachments = fields.List(fields.Dict(), load_default=list)
    extra_properties = fields.Dict(load_default=dict)
    recurrence_rule = fields.Dict(load_default=None, allow_none=True)
    recurrence_exceptions = fields.List(fields.String(), load_default=list)


class CalendarTaskPatchSchema(Schema):
    """Request body for partially updating a VTODO. All fields optional."""

    title = fields.String()
    description = fields.String(allow_none=True)
    date_start = fields.String(allow_none=True)
    due = fields.String(allow_none=True)
    status = fields.String(allow_none=True)
    visibility = fields.String(allow_none=True)
    priority = fields.Integer(validate=validate.Range(min=0, max=9))
    percent_complete = fields.Integer(allow_none=True, validate=validate.Range(min=0, max=100))
    completed_at = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    reminders = fields.List(fields.Dict())
    organizer = fields.Dict(allow_none=True)
    attendees = fields.List(fields.Dict())
    related_to = fields.List(fields.Dict())
    attachments = fields.List(fields.Dict())
    extra_properties = fields.Dict()
    recurrence_rule = fields.Dict(allow_none=True)
    recurrence_exceptions = fields.List(fields.String())


class CalendarTaskResponseSchema(ApiBaseResponse):
    """Response schema for a single VTODO."""

    data = fields.Nested(CalendarTaskSchema, allow_none=True)


class CalendarTaskListDataSchema(Schema):
    """Data payload for the task list response."""

    tasks = fields.List(fields.Nested(CalendarTaskSchema))
    total_count = fields.Integer()


class CalendarTaskListResponseSchema(ApiBaseResponse):
    """Response schema for a list of VTODOs."""

    data = fields.Nested(CalendarTaskListDataSchema, allow_none=True)
