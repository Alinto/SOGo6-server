#!/usr/bin/env python3
"""
Test script for the updated VacationSchema with DateTimeWithTzField support.
Tests various datetime formats with and without timezone information.
"""

from app.api.v1.mail.schemas.filter import (
    DateTimeWithTzField, VacationSchema, VacationPayloadSchema
)
from marshmallow import ValidationError


def test_datetimewithtzfield():
    """Test DateTimeWithTzField parsing."""
    field = DateTimeWithTzField()
    
    test_cases = [
        # (input, description)
        ("2026-06-15", "Date only"),
        ("2026-06-15T14:30:00", "DateTime without timezone"),
        ("2026-06-15T14:30:00Z", "DateTime with UTC (Z marker)"),
        ("2026-06-15T14:30:00+0100", "DateTime with +HH:MM timezone"),
        ("2026-06-15T14:30:00+01:00", "DateTime with +HH:MM:SS timezone"),
        ("2026-06-15T14:30:00-0500", "DateTime with -HH:MM timezone"),
        ("2026-06-15T14:30:00:Europe/Paris", "DateTime with :Zone timezone"),
        (None, "None value"),
        ("", "Empty string"),
    ]
    
    print("Testing DateTimeWithTzField:")
    print("-" * 60)
    
    for value, description in test_cases:
        try:
            result = field.deserialize(value, None, {})
            print(f"✓ {description:40} -> {result}")
        except ValidationError as e:
            print(f"✗ {description:40} -> ERROR: {e}")
    
    print()


def test_vacation_schema():
    """Test VacationSchema with timezone support."""
    schema = VacationSchema()
    
    test_cases = [
        {
            "name": "Complete vacation with explicit timezone in dates",
            "data": {
                "enabled": 1,
                "custom_subject_enabled": True,
                "custom_subject": "Out of office",
                "auto_reply_text": "I am away",
                "start_date": "2026-06-15T09:00:00+0100",
                "end_date": "2026-06-20T17:00:00:Europe/Paris",
                "timezone": "Europe/Paris",
                "always_send": 0,
                "start_time": "09:00",
                "end_time": "18:00",
                "weekdays_enabled": True,
                "days": [0, 1, 2]
            }
        },
        {
            "name": "Vacation with date-only (no timezone)",
            "data": {
                "enabled": 1,
                "custom_subject_enabled": False,
                "custom_subject": "",
                "auto_reply_text": "Out of office",
                "start_date": "2026-06-15",
                "end_date": "2026-06-20",
                "timezone": "UTC",
                "always_send": 0,
            }
        },
        {
            "name": "Minimal vacation",
            "data": {
                "enabled": 0,
            }
        }
    ]
    
    print("Testing VacationSchema:")
    print("-" * 60)
    
    for test in test_cases:
        try:
            result = schema.load(test["data"])
            print(f"✓ {test['name']}")
            print(f"  Loaded: {result}")
        except ValidationError as e:
            print(f"✗ {test['name']}")
            print(f"  ERROR: {e}")
        print()


def test_vacation_payload_schema():
    """Test VacationPayloadSchema with nested validation."""
    schema = VacationPayloadSchema()
    
    payload = {
        "Vacation": {
            "enabled": 1,
            "custom_subject_enabled": True,
            "custom_subject": "Vacations",
            "auto_reply_text": "I'm on vacation",
            "start_date": "2026-06-15T09:00:00:Europe/Paris",
            "end_date": "2026-06-20T17:00:00Z",
            "timezone": "Europe/Paris",
            "always_send": 0,
            "start_time": "09:00",
            "end_time": "18:00",
            "weekdays_enabled": True,
            "days": [0, 1, 2, 3, 4]
        }
    }
    
    print("Testing VacationPayloadSchema:")
    print("-" * 60)
    
    try:
        result = schema.load(payload)
        print(f"✓ Payload validated successfully")
        print(f"  Loaded: {result}")
        
        # Test dump/serialization
        dumped = schema.dump(result)
        print(f"\n✓ Payload serialized successfully")
        print(f"  Dumped: {dumped}")
    except ValidationError as e:
        print(f"✗ Payload validation failed")
        print(f"  ERROR: {e}")
    print()


def test_example():
    """Test the schema example."""
    print("Testing VacationPayloadSchema.example():")
    print("-" * 60)
    
    example = VacationPayloadSchema.example()
    schema = VacationPayloadSchema()
    
    try:
        result = schema.load(example)
        print(f"✓ Example is valid")
        print(f"  Example: {example}")
    except ValidationError as e:
        print(f"✗ Example is invalid")
        print(f"  ERROR: {e}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Vacation Schema Tests")
    print("=" * 60)
    print()
    
    test_datetimewithtzfield()
    test_vacation_schema()
    test_vacation_payload_schema()
    test_example()
    
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)
