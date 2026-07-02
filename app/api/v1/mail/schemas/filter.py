from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from marshmallow import Schema, ValidationError, fields, validate
from marshmallow.validate import Email
from app.utils.api.ApiBaseResponse import ApiBaseResponse


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
    "subject",
    "from",
    "to",
    "header",
    "body",
    "size",
    "cc",
    "cc or to",
]

# Valid operator names for filter rules
# Note: "over" and "under" are only valid with field="size"
VALID_FILTER_OPERATORS = [
    "contains",
    "is",
    "matches",
    "regex",
    "notcontains",
    "exists",
    "over",
    "under",
]

# Valid action methods for filter actions
VALID_ACTION_METHODS = [
    "fileinto",
    "redirect",
    "reject",
    "discard",
    "keep",
    "imapflags",
    "notify",
]


class FilterRuleSchema(Schema):
    """
    A single rule condition or a nested group of rules.
    When ``op`` is present this node is a group; otherwise it is a leaf condition.
    """
    op            = fields.String()             # "and" | "or" — group node
    rules         = fields.List(fields.Dict())  # nested rules — group node
    field         = fields.String(validate=validate.OneOf(VALID_FILTER_FIELDS))  # subject | from | to | header | body | size
    operator      = fields.String(validate=validate.OneOf(VALID_FILTER_OPERATORS))  # contains | is | matches | regex | notcontains | exists | over | under
    custom_header = fields.String()             # used when field == "header"
    value         = fields.String()             # value to match against or number for :count/:size
    case_sensitive = fields.Boolean(load_default=True, dump_default=True)  # For string comparisons

    def __post_load__(self, data: dict, **kwargs: Any) -> dict:
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
    folders            = fields.List(fields.String(), load_default=[], dump_default=[])  # Folders list
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

    def __post_load__(self, data: dict, **kwargs: Any) -> dict:
        """Filter out empty strings from lists.
        
        Ensures that folders and addresses lists contain only non-empty strings.
        
        :param data: The deserialized data
        :type data: dict
        :return: The validated and cleaned data
        :rtype: dict
        """
        # Filter out empty strings from folders list
        if data.get("folders"):
            data["folders"] = [f for f in data["folders"] if f and isinstance(f, str)]
        
        # Filter out empty strings from addresses list
        if data.get("addresses"):
            data["addresses"] = [a for a in data["addresses"] if a and isinstance(a, str)]
        
        return data


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
    customSubjectEnabled   = fields.Boolean(load_default=False, dump_default=False)
    customSubject          = fields.String(load_default="", dump_default="")
    autoReplyText          = fields.String(load_default="", dump_default="")
    startDate              = DateTimeWithTzField(load_default=None, dump_default=None, allow_none=True)
    endDate                = DateTimeWithTzField(load_default=None, dump_default=None, allow_none=True)
    timezone               = fields.String(load_default=None, dump_default=None, allow_none=True, metadata={"description": "IANA timezone (e.g., 'Europe/Paris', 'UTC'). Used for startDate/endDate when they don't have explicit timezone."})
    alwaysSend             = fields.Boolean(load_default=False, dump_default=False)
    ignoreLists            = fields.Boolean(load_default=False, dump_default=False)
    startTime              = fields.String(load_default=None, dump_default=None, allow_none=True)
    endTime                = fields.String(load_default=None, dump_default=None, allow_none=True)
    weekdaysEnabled        = fields.Boolean(load_default=False, dump_default=False)
    days                   = fields.List(fields.Integer(), load_default=[], dump_default=[])


class ForwardSchema(Schema):
    """Mail forwarding settings."""
    forwardAddress = fields.List(fields.Email(), load_default=[], dump_default=[])
    enabled        = fields.Boolean(load_default=False, dump_default=False)
    keepCopy       = fields.Boolean(load_default=False, dump_default=False)
    alwaysSend     = fields.Boolean(load_default=False, dump_default=False)


class NotificationSchema(Schema):
    """Mail notification settings (RFC 5435 - Sieve Notify Extension).
    
    Allows users to configure email notifications when mail filters are triggered.
    """
    enabled              = fields.Boolean(load_default=False, dump_default=False)
    notifyAddresses      = fields.List(fields.Email(), load_default=[], dump_default=[])
    notifyMessage        = fields.String(load_default="", dump_default="")


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
                                "case_sensitive": False
                            },
                            {
                                "field": "subject",
                                "operator": "contains",
                                "value": "urgent",
                                "case_sensitive": False
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
                        "case_sensitive": False
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
                                "case_sensitive": False
                            },
                            {
                                "field": "subject",
                                "operator": "contains",
                                "value": "[NOTIFICATION]",
                                "case_sensitive": False
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
                                "case_sensitive": False
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
                            "method": "imapflags",
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
                                "case_sensitive": False
                            },
                            {
                                "field": "from",
                                "operator": "contains",
                                "value": "marketing@",
                                "case_sensitive": False
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
                                "case_sensitive": False
                            },
                            {
                                "op": "and",
                                "rules": [
                                    {
                                        "field": "subject",
                                        "operator": "contains",
                                        "value": "[IMPORTANT]",
                                        "case_sensitive": False
                                    },
                                    {
                                        "field": "from",
                                        "operator": "contains",
                                        "value": "team@company.com",
                                        "case_sensitive": False
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
                                "case_sensitive": False
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
                                "case_sensitive": False
                            }
                        ]
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
                "customSubjectEnabled": True,
                "customSubject": "Out of office",
                "autoReplyText": "I am away until Monday.",
                "startDate": "2026-06-15T09:00:00+0100",
                "endDate": "2026-06-20T17:00:00",
                "timezone": "Europe/Paris",
                "alwaysSend": False,
                "ignoreLists": True,
                "startTime": "18:00",
                "endTime": "08:00",
                "weekdaysEnabled": True,
                "days": [0, 3, 5]
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
                "forwardAddress": ["toma@gmail.com"],
                "enabled": True,
                "keepCopy": True,
                "alwaysSend": True
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
                "notifyAddresses": ["admin@example.com", "alerts@example.com"],
                "notifyMessage": "A mail filter has been triggered on your account"
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
