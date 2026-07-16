"""Base validators for calendar schemas (events and tasks)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from marshmallow import Schema, ValidationError, validates_schema

from app.utils.errors import ERROR_CALENDAR_END_BEFORE_START


class DatesValidationSchema(Schema):
    """Base schema class that provides date validation for calendar items (events and tasks).
    
    Validates that the end date is not earlier than the start date.
    This validation applies to:
    - Events: validates date_start and date_end
    - Tasks: validates date_start and date_due
    """

    @validates_schema
    def validate_dates(self, data: dict, **kwargs: Any) -> None:
        """Validate that end date is not earlier than start date."""
        # Get the start and end date fields (works for both events and tasks)
        date_start = data.get("date_start")
        # Try both 'date_end' (events) and 'date_due' (tasks)
        date_end = data.get("date_end") or data.get("date_due")

        if date_start and date_end:
            start_dt: datetime = datetime.fromisoformat(date_start.replace('Z', '+00:00'))
            end_dt: datetime = datetime.fromisoformat(date_end.replace('Z', '+00:00'))
            if end_dt < start_dt:
                raise ValidationError(ERROR_CALENDAR_END_BEFORE_START.m)
