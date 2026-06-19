"""Nested schemas describing the structure of event/calendar sub-objects.

These replace the opaque ``fields.Dict()`` so the OpenAPI documentation tells the
API user exactly what each sub-object contains. They follow the same style as the
mail API schemas: described fields, ``required`` on the mandatory ones and
``validate.OneOf`` on the enum ones.

This duplicates part of the validation done by the deserializer and the domain model
(which run for every caller, including non-API ones such as the agent) - that is
intentional, to give API clients a precise contract: ``required`` on the mandatory
fields and ``validate.OneOf`` on the enum ones, same as the mail API schemas. Unknown
keys are rejected (Marshmallow default), which also matches the mail API.
"""
from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.RelationType import RelationType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod

_ROLE_VALUES = [r.value for r in AttendeeRole]
_STATUS_VALUES = [s.value for s in AttendeeStatus]
_CUTYPE_VALUES = [c.value for c in CalUserType]
_METHOD_VALUES = [m.value for m in ReminderMethod]
_RELATION_VALUES = [r.value for r in RelationType]
_FREQUENCY_VALUES = [f.value for f in RecurrenceFrequency]


class OrganizerSchema(Schema):
    """Event organizer (RFC 5545 ORGANIZER)."""

    email = fields.String(required=True, metadata={"description": "Organizer email address."})
    name = fields.String(allow_none=True)
    role = fields.String(allow_none=True, validate=validate.OneOf(_ROLE_VALUES))
    status = fields.String(allow_none=True, validate=validate.OneOf(_STATUS_VALUES))
    sent_by = fields.String(allow_none=True)
    dir_ref = fields.String(allow_none=True)


class AttendeeSchema(Schema):
    """Event attendee (RFC 5545 ATTENDEE)."""

    email = fields.String(required=True, metadata={"description": "Attendee email address."})
    name = fields.String(allow_none=True)
    role = fields.String(validate=validate.OneOf(_ROLE_VALUES))
    status = fields.String(validate=validate.OneOf(_STATUS_VALUES))
    rsvp = fields.Boolean(metadata={"description": "Whether a response is requested."})
    cutype = fields.String(validate=validate.OneOf(_CUTYPE_VALUES))
    delegated_from = fields.String(allow_none=True)
    delegated_to = fields.String(allow_none=True)
    sent_by = fields.String(allow_none=True)
    dir_ref = fields.String(allow_none=True)


class ReminderSchema(Schema):
    """Event reminder / alarm (RFC 5545 VALARM)."""

    method = fields.String(required=True, validate=validate.OneOf(_METHOD_VALUES))
    minutes_before = fields.Integer(load_default=None, allow_none=True,
                                    metadata={"description": "Minutes before the start when the reminder fires. "
                                                             "Optional: when omitted, the parent calendar's "
                                                             "default_alarm_duration_min (or the global default) is used."})


class EventRelationSchema(Schema):
    """Relationship to another component (RFC 5545 RELATED-TO)."""

    uid = fields.String(required=True, metadata={"description": "UID of the related component."})
    relation_type = fields.String(validate=validate.OneOf(_RELATION_VALUES))


class AttachmentCalendarSchema(Schema):
    """Event attachment (RFC 5545 ATTACH)."""

    filename = fields.String(allow_none=True)
    mime_type = fields.String(allow_none=True)
    url = fields.String(allow_none=True)
    size = fields.Integer(allow_none=True, metadata={"description": "Size in bytes."})


class ConferenceEntryPointSchema(Schema):
    """A single way to join the conference (RFC 7986 CONFERENCE entry point)."""

    type = fields.String(required=True, metadata={"description": "e.g. video | phone | sip."})
    uri = fields.String(required=True)
    label = fields.String(allow_none=True)


class ConferenceDataSchema(Schema):
    """Conferencing information (RFC 7986 CONFERENCE)."""

    type = fields.String(required=True, metadata={"description": "Conference type, e.g. video | phone."})
    url = fields.String(allow_none=True)
    conference_id = fields.String(allow_none=True)
    entry_points = fields.List(fields.Nested(ConferenceEntryPointSchema), load_default=list)


class RecurrenceRuleSchema(Schema):
    """Recurrence rule (RFC 5545 RRULE)."""

    frequency = fields.String(required=True, validate=validate.OneOf(_FREQUENCY_VALUES))
    interval = fields.Integer(metadata={"description": "Interval between occurrences (default 1)."})
    until = fields.String(allow_none=True, metadata={"description": "ISO 8601 UTC datetime; mutually exclusive with count."})
    count = fields.Integer(allow_none=True, metadata={"description": "Number of occurrences; mutually exclusive with until."})
    by_day = fields.List(fields.String(), allow_none=True, metadata={"description": "Days, e.g. [MO, WE, FR] or [2MO]."})
    by_month_day = fields.List(fields.Integer(), allow_none=True)
    by_month = fields.List(fields.Integer(), allow_none=True)
    by_year_day = fields.List(fields.Integer(), allow_none=True)
    by_week_no = fields.List(fields.Integer(), allow_none=True)
    by_set_pos = fields.List(fields.Integer(), allow_none=True)
    by_hour = fields.List(fields.Integer(), allow_none=True)
    by_minute = fields.List(fields.Integer(), allow_none=True)
    by_second = fields.List(fields.Integer(), allow_none=True)
    week_start = fields.String(allow_none=True, metadata={"description": "Week start day, e.g. MO."})


class DatesWithTzSchema(Schema):
    """Event start/end rendered in the event and calendar timezones (read-only helper)."""

    date_start_tz_event = fields.String(allow_none=True)
    date_end_tz_event = fields.String(allow_none=True)
    date_start_tz_calendar = fields.String(allow_none=True)
    date_end_tz_calendar = fields.String(allow_none=True)


class CalendarPermissionsSchema(Schema):
    """Resolved ACL permissions for the requesting user (read-only)."""

    public_level = fields.String(metadata={"description": "none | view_datetime | view_all | respond | modify"})
    confidential_level = fields.String(metadata={"description": "none | view_datetime | view_all | respond | modify"})
    private_level = fields.String(metadata={"description": "none | view_datetime | view_all | respond | modify"})
    can_create = fields.Boolean()
    can_delete = fields.Boolean()


class SyncConfigUpdateSchema(Schema):
    """Partial external-calendar sync configuration update."""

    url = fields.Url(metadata={"description": "Remote .ics URL."})
    sync_interval_minutes = fields.Integer(
        validate=validate.Range(min=5, max=1440),
        metadata={"description": "Sync interval in minutes (min 5, max 1440)."},
    )


class SyncResultSchema(Schema):
    """Counters returned after an external-calendar sync."""

    inserted = fields.Integer()
    updated = fields.Integer()
    deleted = fields.Integer()
    total = fields.Integer()
    skipped = fields.Integer()
