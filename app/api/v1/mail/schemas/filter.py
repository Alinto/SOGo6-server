from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from marshmallow import Schema, ValidationError, fields, validate, validates_schema, post_load
from marshmallow.validate import Email
from app.utils.api.ApiBaseResponse import ApiBaseResponse
from app.utils import constants as cs


# ---------------------------------------------------------------------------
# Custom DateTime field for vacation dates with timezone support
# ---------------------------------------------------------------------------

class DateTimeWithTzField(fields.Field):
    """DateTime field that accepts date-only, datetime, or datetime with timezone.
    
    Supports formats:
    - Date only: "2026-06-15" (date only)
    - DateTime: "2026-06-15T14:30:00" (no timezone)
    - DateTime with timezone: "2026-06-15T14:30:00+0100" or "2026-06-15T14:30:00:Europe/Paris"
    - DateTime with Z: "2026-06-15T14:30:00Z" (UTC)
    
    Returns the value as-is (preserving the string format and timezone information)
    to be processed by the vacation handler with proper timezone context.
    """

    def _deserialize(self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs: Any) -> str | None:
        """Deserialize a date/datetime value with optional timezone.
        
        Validates the format but returns as-is for later processing.
        """
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValidationError("Must be a string in ISO 8601 format.")

        value = value.strip()
        if not value:
            return None

        # Validate format by trying to parse it
        try:
            # Format: date only (YYYY-MM-DD)
            if len(value) == 10 and value.count("-") == 2:
                datetime.strptime(value, "%Y-%m-%d")
                return value

            # Format: with T (datetime variations)
            if "T" not in value:
                raise ValidationError("Invalid date/datetime format: must contain 'T' for datetime or be YYYY-MM-DD for date.")

            date_part, time_part = value.split("T", 1)

            # Validate date part
            datetime.strptime(date_part, "%Y-%m-%d")

            time_part_base = time_part
            has_tz = False

            # Check for Z (UTC)
            if time_part_base.endswith("Z"):
                time_part_base = time_part_base[:-1]
                has_tz = True
            # Check for +/- timezone offset
            elif "+" in time_part_base:
                idx = time_part_base.rfind("+")
                time_part_base = time_part_base[:idx]
                has_tz = True
            elif time_part_base.count("-") > 0:
                idx = time_part_base.rfind("-")
                if idx > 7:  # After HH:MM:SS minimum
                    time_part_base = time_part_base[:idx]
                    has_tz = True
            elif ":" in time_part_base and time_part_base.count(":") > 2:
                # Check for :Zone format
                parts = time_part_base.rsplit(":", 1)
                tz_candidate = parts[1]
                if "/" in tz_candidate or tz_candidate.startswith("UTC") or tz_candidate.startswith("GMT"):
                    time_part_base = parts[0]
                    has_tz = True

            # Validate the time part (HH:MM:SS or HH:MM:SS.ffffff)
            # Try to parse it
            try:
                if "." in time_part_base:
                    datetime.strptime(time_part_base, "%H:%M:%S.%f")
                else:
                    datetime.strptime(time_part_base, "%H:%M:%S")
            except ValueError:
                # Try simpler format (HH:MM)
                try:
                    datetime.strptime(time_part_base, "%H:%M")
                except ValueError:
                    raise ValidationError(f"Invalid time format in: {value}")

            # If we got here, the format is valid
            return value

        except (ValueError, TypeError, AttributeError) as e:
            raise ValidationError(f"Invalid date/datetime format: {str(e)}") from e


# ---------------------------------------------------------------------------
# Filter rules & actions
# ---------------------------------------------------------------------------

# Valid field names for filter rules
VALID_FILTER_FIELDS = [
    cs.FILTER_FIELD_SUBJECT,
    cs.FILTER_FIELD_FROM,
    cs.FILTER_FIELD_TO,
    cs.FILTER_FIELD_CC,
    cs.FILTER_FIELD_TO_OR_CC,
    cs.FILTER_FIELD_HEADER,
    cs.FILTER_FIELD_BODY,
    cs.FILTER_FIELD_SIZE,
]

# Valid operator names for filter rules
# Note: "FILTER_OP_OVER" and "FILTER_OP_UNDER" are only valid with field FILTER_FIELD_SIZE
# Note: "FILTER_OP_EXISTS" and "FILTER_OP_EXISTS_NOT" are only valid with field FILTER_FIELD_HEADER
VALID_FILTER_OPERATORS = [
    cs.FILTER_OP_IS,
    cs.FILTER_OP_IS_NOT,
    cs.FILTER_OP_CONTAINS,
    cs.FILTER_OP_CONTAINS_NOT,
    cs.FILTER_OP_MATCHES,
    cs.FILTER_OP_MATCHES_NOT,
    cs.FILTER_OP_REGEX,
    cs.FILTER_OP_REGEX_NOT,
    cs.FILTER_OP_EXISTS,
    cs.FILTER_OP_EXISTS_NOT,
    cs.FILTER_OP_OVER,
    cs.FILTER_OP_UNDER,
]

# Valid action methods for filter actions
VALID_ACTION_METHODS = [
    cs.FILTER_ACTION_FILEINTO,
    cs.FILTER_ACTION_REDIRECT,
    cs.FILTER_ACTION_REJECT,
    cs.FILTER_ACTION_DISCARD,
    cs.FILTER_ACTION_KEEP,
    cs.FILTER_ACTION_FLAG,
    cs.FILTER_ACTION_NOTIFY,
    cs.FILTER_ACTION_STOP
]


class FilterRuleSchema(Schema):
    """
    A single rule condition or a nested group of rules.
    When ``op`` is present this node is a group; otherwise it is a leaf condition.
    """
    op            = fields.String(validate=validate.OneOf(('and', 'or')))             # "and" | "or" — group node
    rules         = fields.List(fields.Dict())  # nested rules — group node
    field         = fields.String(validate=validate.OneOf(VALID_FILTER_FIELDS))
    operator      = fields.String(validate=validate.OneOf(VALID_FILTER_OPERATORS))
    custom_header = fields.String()             # used when field == cs.FILTER_FIELD_HEADER
    value         = fields.String()             # value to match against or number for :count/:size

    @validates_schema
    def check_over_unser(self, data: dict, **kwargs: Any) -> dict:
        """Validate that 'over' and 'under' operators are only used with 'size' field.
        
        :param data: The deserialized data
        :type data: dict
        :raises ValidationError: If over/under is used with non-size field
        :return: The validated data
        :rtype: dict
        """
        # Only validate leaf nodes (rules without nested rules)
        if "op" not in data and "rules" not in data:
            operator = data.get("operator", "").lower()
            field = data.get("field", "")

            # Check if using size-specific operators with non-size field
            if operator in ("over", "under") and field != "size":
                raise ValidationError(
                    f"Operator '{operator}' can only be used with field='size', but got field='{field}'"
                )

            # Check if using size field with non-size operators
            if field == "size" and operator not in ("over", "under"):
                raise ValidationError(
                    f"Field 'size' can only be used with operators 'over' or 'under', but got operator='{operator}'"
                )

        return data


class FilterActionArgumentsSchema(Schema):
    """Arguments for a filter action.
    
    Note: In Sieve, "copy" is not a standalone action but a flag (:copy) applied to fileinto.
    Use method="fileinto" with keep_copy=True to achieve the copy behavior.
    
    For redirect with multiple addresses, provide "addresses" as a list.
    In Sieve, each address will generate a separate "redirect" action.
    """
    # fileinto action arguments
    folders            = fields.List(fields.String(validate=validate.Length(min=1)), load_default=[], dump_default=[])  # Folders list
    create_if_no_exist = fields.Boolean()
    keep_copy          = fields.Boolean(load_default=False, dump_default=False)  # Sieve :copy flag
    # redirect action arguments
    addresses          = fields.List(fields.Email(), load_default=[], dump_default=[])  # Email addresses for redirect
    # reject action arguments
    message            = fields.String()  # Only used for reject action
    # imapflags action
    flags              = fields.List(fields.String())
    # notify action
    method             = fields.String()  # e.g. "mailto"
    priority           = fields.String()  # e.g. "normal", "urgent", "low"
    message_text       = fields.String()  # Alternative message for notify


class FilterSchema(Schema):
    """A single filter action."""
    method    = fields.String(validate=validate.OneOf(VALID_ACTION_METHODS))
    arguments = fields.Nested(FilterActionArgumentsSchema, load_default={}, dump_default={})


class FilterItemSchema(Schema):
    """A single mail filter rule."""
    name    = fields.String(required=True)
    enabled = fields.Boolean(load_default=True, dump_default=True)
    actions = fields.List(fields.Nested(FilterSchema), required=True)
    rules   = fields.Nested(FilterRuleSchema, required=True)


# ---------------------------------------------------------------------------
# Vacation / Forward / Notification sub-schemas
# ---------------------------------------------------------------------------

class VacationSchema(Schema):
    """Auto-reply (vacation) settings."""

    enabled                = fields.Boolean(load_default=False, dump_default=False)
    custom_subject_enabled = fields.Boolean(load_default=False, dump_default=False)
    custom_subject         = fields.String(load_default="", dump_default="")
    auto_reply_text        = fields.String(load_default="", dump_default="")
    start_date             = DateTimeWithTzField(load_default=None, dump_default=None, allow_none=True)
    end_date               = DateTimeWithTzField(load_default=None, dump_default=None, allow_none=True)
    timezone               = fields.String(load_default=None, dump_default=None, allow_none=True,
                                           metadata={"description": "IANA timezone (e.g., 'Europe/Paris', 'UTC'). Used for "
                                           "start_date/end_date when they don't have explicit timezone."})
    always_send            = fields.Boolean(load_default=False, dump_default=False,
                                             metadata={"description": "If True, the vacation rule is processed before regular "
                                             "filter rules and always sends replies (takes priority over other filters)."})
    start_time             = fields.String(load_default=None, dump_default=None, allow_none=True)
    end_time               = fields.String(load_default=None, dump_default=None, allow_none=True)
    weekdays_enabled       = fields.Boolean(load_default=False, dump_default=False)
    weekday                = fields.List(fields.Integer(), load_default=[], dump_default=[],
                                         metadata={"description": "List of weekday numbers (0-6, where 0 is Sunday). Only applies when weekdays_enabled is True."})
    days                   = fields.Integer(load_default=None, dump_default=None, allow_none=True,
                                            validate=validate.Range(min=0),
                                            metadata={"description": "Minimum delay in days between vacation responses (RFC 5230 :days)."
                                            " If set, prevents sending duplicate vacation replies within this period. Must be > 0, or = 0 "
                                            "if SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS is enabled."})


class ForwardSchema(Schema):
    """Mail forwarding settings."""
    forward_address = fields.List(fields.Email(), load_default=[], dump_default=[])
    enabled        = fields.Boolean(load_default=False, dump_default=False)
    keep_copy       = fields.Boolean(load_default=False, dump_default=False)
    always_send     = fields.Boolean(load_default=False, dump_default=False)


class NotificationSchema(Schema):
    """Mail notification settings (RFC 5435 - Sieve Notify Extension).
    
    Allows users to configure email notifications when mail filters are triggered.
    """
    enabled              = fields.Boolean(load_default=False, dump_default=False)
    notify_addresses      = fields.List(fields.Email(), load_default=[], dump_default=[])
    notify_message        = fields.String(load_default="", dump_default="")


# ---------------------------------------------------------------------------
# Per-endpoint payload schemas
# ---------------------------------------------------------------------------

class FiltersPayloadSchema(Schema):
    """POST /filters — replaces the ``filters`` list in the stored column."""
    filters = fields.List(fields.Nested(FilterItemSchema), required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema showing various filter conditions and actions.
        Demonstrates multiple folders with fileinto, the keep_copy flag, and redirect with multiple addresses.
        """
        return {
            "filters": [
                {
                    "name": "Move from CEO with urgent subject to INBOX",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "fileinto",
                            "arguments": {
                                "folders": ["INBOX"],
                                "create_if_no_exist": True
                            }
                        }
                    ],
                    "rules": {
                        "op": "and",
                        "rules": [
                            {
                                "field": "from",
                                "operator": "contains",
                                "value": "ceo@company.com",
                            },
                            {
                                "field": "subject",
                                "operator": "contains",
                                "value": "urgent",
                            }
                        ]
                    }
                },
                {
                    "name": "Redirect external mail to multiple addresses",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "redirect",
                            "arguments": {
                                "addresses": ["admin@example.com", "boss@example.com"]
                            }
                        }
                    ],
                    "rules": {
                        "field": "from",
                        "operator": "notcontains",
                        "value": "@company.com",
                    }
                },
                {
                    "name": "Alerts or notifications to multiple folders",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "fileinto",
                            "arguments": {
                                "folders": ["Alertes", "Notifications"],
                                "create_if_no_exist": True,
                                "keep_copy": True
                            }
                        }
                    ],
                    "rules": {
                        "op": "or",
                        "rules": [
                            {
                                "field": "subject",
                                "operator": "contains",
                                "value": "[ALERTE]",
                            },
                            {
                                "field": "subject",
                                "operator": "contains",
                                "value": "[NOTIFICATION]",
                            }
                        ]
                    }
                },
                {
                    "name": "Large attachments from external senders",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "fileinto",
                            "arguments": {
                                "folders": ["Archive"],
                                "create_if_no_exist": True
                            }
                        }
                    ],
                    "rules": {
                        "op": "and",
                        "rules": [
                            {
                                "field": "size",
                                "operator": "over",
                                "value": "5M"
                            },
                            {
                                "field": "from",
                                "operator": "notcontains",
                                "value": "@company.com",
                            }
                        ]
                    }
                },
                {
                    "name": "Marketing emails with specific header",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "fileinto",
                            "arguments": {
                                "folders": ["Marketing"],
                                "create_if_no_exist": True
                            }
                        },
                        {
                            "method": "addflag",
                            "arguments": {
                                "flags": ["\\Flagged"]
                            }
                        }
                    ],
                    "rules": {
                        "op": "and",
                        "rules": [
                            {
                                "field": "header",
                                "operator": "contains",
                                "custom_header": "X-Marketing-Campaign",
                                "value": "summer2026",
                            },
                            {
                                "field": "from",
                                "operator": "contains",
                                "value": "marketing@",
                            }
                        ]
                    }
                },
                {
                    "name": "Complex rule: projects OR important AND from team",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "fileinto",
                            "arguments": {
                                "folders": ["Work"],
                                "create_if_no_exist": True
                            }
                        }
                    ],
                    "rules": {
                        "op": "or",
                        "rules": [
                            {
                                "field": "subject",
                                "operator": "contains",
                                "value": "[PROJECT]",
                            },
                            {
                                "op": "and",
                                "rules": [
                                    {
                                        "field": "subject",
                                        "operator": "contains",
                                        "value": "[IMPORTANT]",
                                    },
                                    {
                                        "field": "from",
                                        "operator": "contains",
                                        "value": "team@company.com",
                                    }
                                ]
                            }
                        ]
                    }
                },
                {
                    "name": "Body content with size constraint AND specific recipient",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "fileinto",
                            "arguments": {
                                "folders": ["Important"],
                                "create_if_no_exist": True
                            }
                        }
                    ],
                    "rules": {
                        "op": "and",
                        "rules": [
                            {
                                "field": "body",
                                "operator": "contains",
                                "value": "urgent action required",
                            },
                            {
                                "field": "size",
                                "operator": "under",
                                "value": "10M"
                            },
                            {
                                "field": "to",
                                "operator": "contains",
                                "value": "team@company.com",
                            }
                        ]
                    }
                },
                {
                    "name": "Discard spam emails",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "discard",
                            "arguments": {}
                        }
                    ],
                    "rules": {
                        "field": "subject",
                        "operator": "contains",
                        "value": "SPAM"                
                    }
                },
                {
                    "name": "Reject emails from blocked domain",
                    "enabled": True,
                    "actions": [
                        {
                            "method": "reject",
                            "arguments": {
                                "message": "Emails from this domain are not accepted"
                            }
                        }
                    ],
                    "rules": {
                        "field": "from",
                        "operator": "contains",
                        "value": "@blocked-domain.com",
                    }
                }
            ]
        }


class VacationPayloadSchema(Schema):
    """POST /vacation — replaces the ``Vacation`` section in the stored column."""
    Vacation = fields.Nested(VacationSchema, required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "Vacation": {
                "enabled": True,
                "custom_subject_enabled": True,
                "custom_subject": "Out of office",
                "auto_reply_text": "I am away until Monday.",
                "start_date": "2026-06-15T09:00:00+0100",
                "end_date": "2026-06-20T17:00:00",
                "timezone": "Europe/Paris",
                "always_send": True,
                "start_time": "18:00",
                "end_time": "08:00",
                "weekdays_enabled": True,
                "weekday": [0, 3, 5],
                "days": 1
            }
        }


class ForwardPayloadSchema(Schema):
    """POST /forward — replaces the ``Forward`` section in the stored column."""
    Forward = fields.Nested(ForwardSchema, required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "Forward": {
                "forward_address": ["toma@gmail.com"],
                "enabled": True,
                "keep_copy": True,
                "always_send": True
            }
        }


class NotificationPayloadSchema(Schema):
    """POST /notify — replaces the ``Notification`` section in the stored column."""
    Notification = fields.Nested(NotificationSchema, required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "Notification": {
                "enabled": True,
                "notify_addresses": ["admin@example.com", "alerts@example.com"],
                "notify_message": "A mail filter has been triggered on your account"
            }
        }


# ---------------------------------------------------------------------------
# Shared response schema (returns the full updated filters column content)
# ---------------------------------------------------------------------------

class FiltersSetResponseSchema(ApiBaseResponse):
    """Response for all four filter-related POST endpoints."""
    data = fields.Dict(allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": FiltersPayloadSchema.example()
        }


# ---------------------------------------------------------------------------
# GET response schemas (return only the requested section)
# ---------------------------------------------------------------------------

class FiltersGetResponseSchema(ApiBaseResponse):
    """Response for GET /filters — returns the ``filters`` list."""
    data = fields.Dict(allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": FiltersPayloadSchema.example(),
        }


class VacationGetResponseSchema(ApiBaseResponse):
    """Response for GET /vacation — returns the ``Vacation`` section."""
    data = fields.Dict(allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": VacationPayloadSchema.example(),
        }


class ForwardGetResponseSchema(ApiBaseResponse):
    """Response for GET /forward — returns the ``Forward`` section."""
    data = fields.Dict(allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": ForwardPayloadSchema.example(),
        }


class NotificationGetResponseSchema(ApiBaseResponse):
    """Response for GET /notify — returns the ``Notification`` section."""
    data = fields.Dict(allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for this schema
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": NotificationPayloadSchema.example(),
        }
