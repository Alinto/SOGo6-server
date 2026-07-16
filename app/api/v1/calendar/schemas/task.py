from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.api.v1.calendar.schemas.components import (
    AttachmentCalendarSchema, AttendeeSchema, EventRelationSchema, OrganizerSchema, RecurrenceRuleSchema, ReminderSchema,
)
from app.api.v1.calendar.schemas.utils import DatesValidationSchema
from app.module.calendar.CalendarConst import MAX_EVENT_DESCRIPTION_LENGTH, MAX_EVENT_TITLE_LENGTH
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.utils.api.ApiBaseResponse import ApiBaseResponse
from .event import CalendarEventQueryArgsSchema  # reuse date range / search args

_SEARCH_MAX_LENGTH = 200

_TASK_STATUS_VALUES = EventStatus.task_values()
_VISIBILITY_VALUES = [v.value for v in EventVisibility if v != EventVisibility.UNDEFINED]


class CalendarTaskQueryArgsSchema(CalendarEventQueryArgsSchema):
    """Query parameters for listing tasks (same date range / search as events)."""


class CalendarTaskSchema(Schema):
    """Representation of a single VTODO in API responses."""

    key = fields.String(allow_none=True)
    calendar_key = fields.String(allow_none=True)
    uid = fields.String()
    title = fields.String()
    description = fields.String(allow_none=True)
    date_start = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC start (optional for VTODOs)."})
    date_due = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC due date (maps to RFC 5545 DUE)."})
    status = fields.String(validate=validate.OneOf(_TASK_STATUS_VALUES))
    visibility = fields.String(validate=validate.OneOf(_VISIBILITY_VALUES))
    priority = fields.Integer()
    percent_complete = fields.Integer(allow_none=True)
    completed_at = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    reminders = fields.List(fields.Nested(ReminderSchema))
    organizer = fields.Nested(OrganizerSchema, allow_none=True)
    attendees = fields.List(fields.Nested(AttendeeSchema))
    related_to = fields.List(fields.Nested(EventRelationSchema))
    attachments = fields.List(fields.Nested(AttachmentCalendarSchema))
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String())
    recurrence_rule = fields.Nested(RecurrenceRuleSchema, allow_none=True)
    recurrence_exceptions = fields.List(fields.String())
    component_type = fields.String()
    created_at = fields.String(allow_none=True)
    updated_at = fields.String(allow_none=True)


class CalendarTaskCreateSchema(DatesValidationSchema):
    """Request body for creating a new VTODO."""

    uid = fields.String(load_default=None, allow_none=True)
    title = fields.String(required=True, validate=validate.Length(max=MAX_EVENT_TITLE_LENGTH), metadata={"example": "Prepare the meeting"})
    description = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=MAX_EVENT_DESCRIPTION_LENGTH), metadata={"example": "Agenda and slides"})
    date_start = fields.String(load_default=None, allow_none=True,
                               metadata={"description": "ISO 8601 UTC. Defaults to now if absent.",
                                         "example": "2026-04-22T09:00:00.000Z"})
    date_due = fields.String(load_default=None, allow_none=True,
                        metadata={"description": "ISO 8601 UTC due date (RFC 5545 DUE). No limit if absent.",
                                  "example": "2026-04-23T17:00:00.000Z"})
    status = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(_TASK_STATUS_VALUES),
                           metadata={"example": "needs_action"})
    visibility = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(_VISIBILITY_VALUES),
                               metadata={"example": "public"})
    priority = fields.Integer(load_default=0, validate=validate.Range(min=0, max=9),
                              metadata={"example": 1})
    percent_complete = fields.Integer(load_default=None, allow_none=True,
                                      validate=validate.Range(min=0, max=100),
                                      metadata={"example": 0})
    completed_at = fields.String(load_default=None, allow_none=True)
    categories = fields.List(fields.String(), load_default=list, metadata={"example": []})
    reminders = fields.List(fields.Nested(ReminderSchema), load_default=list, metadata={"example": []})
    organizer = fields.Nested(OrganizerSchema, load_default=None, allow_none=True, metadata={"example": None})
    attendees = fields.List(fields.Nested(AttendeeSchema), load_default=list, metadata={"example": []})
    related_to = fields.List(fields.Nested(EventRelationSchema), load_default=list, metadata={"example": []})
    attachments = fields.List(fields.Nested(AttachmentCalendarSchema), load_default=list, metadata={"example": []})
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String(), load_default=dict, metadata={"example": {}})
    recurrence_rule = fields.Nested(RecurrenceRuleSchema, load_default=None, allow_none=True, metadata={"example": None})
    recurrence_exceptions = fields.List(fields.String(), load_default=list, metadata={"example": []})


class CalendarTaskPatchSchema(DatesValidationSchema):
    """Request body for partially updating a VTODO. All fields optional."""

    title = fields.String(validate=validate.Length(max=MAX_EVENT_TITLE_LENGTH))
    description = fields.String(allow_none=True, validate=validate.Length(max=MAX_EVENT_DESCRIPTION_LENGTH))
    date_start = fields.String(allow_none=True)
    date_due = fields.String(allow_none=True)
    status = fields.String(allow_none=True, validate=validate.OneOf(_TASK_STATUS_VALUES))
    visibility = fields.String(allow_none=True, validate=validate.OneOf(_VISIBILITY_VALUES))
    priority = fields.Integer(validate=validate.Range(min=0, max=9))
    percent_complete = fields.Integer(allow_none=True, validate=validate.Range(min=0, max=100))
    completed_at = fields.String(allow_none=True)
    categories = fields.List(fields.String())
    reminders = fields.List(fields.Nested(ReminderSchema))
    organizer = fields.Nested(OrganizerSchema, allow_none=True)
    attendees = fields.List(fields.Nested(AttendeeSchema))
    related_to = fields.List(fields.Nested(EventRelationSchema))
    attachments = fields.List(fields.Nested(AttachmentCalendarSchema))
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String())
    recurrence_rule = fields.Nested(RecurrenceRuleSchema, allow_none=True)
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
