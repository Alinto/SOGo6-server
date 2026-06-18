"""
Serialization cycle tests: deserialization -> serialization -> comparison.

Strategy for VEVENT examples (1, 2, 3):
  1. RFC deserialization -> CalEvent
  2. Serialization -> iCal text
  3. Verify that VEVENT content lines from the input are present in the output
     (excluding DTSTAMP generated dynamically, and properties that legitimately
     change after UTC conversion).

For non-VEVENT examples (4=VTODO, 5=VJOURNAL, 6=VFREEBUSY):
  The deserializer does not support these components; only the absence of
  exceptions during the deserialize->serialize cycle is verified.

Note: re-serialized content lines differ from the original input on
DTSTAMP (generated at serialization time) and PRODID. All other
VEVENT properties must be invariant after a full cycle.

Source: https://icalendar.org/iCalendar-RFC-5545/4-icalendar-object-examples.html
"""
import re
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.serializer.CalEventDeserializerIcal import CalEventDeserializerIcal
from app.module.calendar.serializer.CalEventSerializerIcal import CalEventSerializerIcal
from app.utils.exceptions import RequestException
from tests.test_calendar.ical_examples import (
    ICAL_EXAMPLE_1,
    ICAL_EXAMPLE_2,
    ICAL_EXAMPLE_3,
    ICAL_EXAMPLE_4,
    ICAL_EXAMPLE_5,
    ICAL_EXAMPLE_6,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vevent_lines(ical_text: str, exclude: frozenset[str] | None = None) -> frozenset[str]:
    """
    Extract VEVENT content lines from an iCal text after unfolding.
    Properties listed in `exclude` are ignored (e.g. DTSTAMP).
    Returns a frozenset for order-independent comparison.
    """
    if exclude is None:
        exclude = frozenset({"DTSTAMP"})
    normalized = ical_text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded = re.sub(r"\n[ \t]", "", normalized)
    lines: set[str] = set()
    in_vevent = False
    for line in unfolded.splitlines():
        if line == "BEGIN:VEVENT":
            in_vevent = True
            continue
        if line == "END:VEVENT":
            in_vevent = False
            continue
        if in_vevent:
            prop_name = re.split(r"[;:]", line)[0].upper()
            if prop_name not in exclude:
                lines.add(line)
    return frozenset(lines)


def _compare_events(a: CalEvent, b: CalEvent) -> None:
    """Assert that the functional fields of two CalEvent instances are identical."""
    assert a.uid == b.uid
    assert a.title == b.title
    assert a.description == b.description
    assert a.location == b.location
    assert a.url == b.url
    assert a.date_start == b.date_start
    assert a.date_end == b.date_end
    assert a.all_day == b.all_day
    # Le timezone est stocke en UTC apres deserialisation TZID : perdu apres un roundtrip
    assert a.status == b.status
    assert a.visibility == b.visibility
    assert a.show_as == b.show_as
    assert sorted(a.categories) == sorted(b.categories)
    assert a.sequence == b.sequence
    # Organizer
    if a.organizer:
        assert b.organizer is not None
        assert a.organizer.email == b.organizer.email
        assert a.organizer.name == b.organizer.name
    else:
        assert b.organizer is None
    # Attendees (comparaison par email)
    assert len(a.attendees) == len(b.attendees)
    emails_a = sorted(att.email for att in a.attendees)
    emails_b = sorted(att.email for att in b.attendees)
    assert emails_a == emails_b
    # Attachments (comparaison par URL)
    assert len(a.attachments) == len(b.attachments)
    urls_a = sorted(att.url or "" for att in a.attachments)
    urls_b = sorted(att.url or "" for att in b.attachments)
    assert urls_a == urls_b


@pytest.fixture
def deserializer():
    return CalEventDeserializerIcal()


@pytest.fixture
def serializer():
    return CalEventSerializerIcal()


# ==========================================================================
# Roundtrip CalEvent - comparaison champs (fiable)
# ==========================================================================

def test_roundtrip_example1_fields(deserializer, serializer):
    event_a = deserializer.deserialize(ICAL_EXAMPLE_1)
    reserialized = serializer.serialize(event_a)
    event_b = deserializer.deserialize(reserialized)
    _compare_events(event_a, event_b)


def test_roundtrip_example2_fields(deserializer, serializer):
    event_a = deserializer.deserialize(ICAL_EXAMPLE_2)
    reserialized = serializer.serialize(event_a)
    event_b = deserializer.deserialize(reserialized)
    _compare_events(event_a, event_b)


def test_roundtrip_example3_fields(deserializer, serializer):
    event_a = deserializer.deserialize(ICAL_EXAMPLE_3)
    reserialized = serializer.serialize(event_a)
    event_b = deserializer.deserialize(reserialized)
    _compare_events(event_a, event_b)


# ==========================================================================
# Roundtrip string - les properties VEVENT de l'input doivent etre presentes
# dans l'output (hors DTSTAMP et ATTENDEE dont les params peuvent differer)
# ==========================================================================

def test_roundtrip_example1_string(deserializer, serializer):
    event_a = deserializer.deserialize(ICAL_EXAMPLE_1)
    reserialized = serializer.serialize(event_a)

    original = _vevent_lines(ICAL_EXAMPLE_1, exclude=frozenset({"DTSTAMP", "ATTENDEE"}))
    output = _vevent_lines(reserialized, exclude=frozenset({"DTSTAMP", "ATTENDEE"}))

    missing = original - output
    assert not missing, f"Properties manquantes apres re-serialisation : {missing}"


def test_roundtrip_example2_string(deserializer, serializer):
    event_a = deserializer.deserialize(ICAL_EXAMPLE_2)
    reserialized = serializer.serialize(event_a)

    # Pour example 2, DTSTART/DTEND sont convertis en UTC apres parsing
    # -> on compare seulement les properties independantes du timezone
    original = _vevent_lines(ICAL_EXAMPLE_2, exclude=frozenset({
        "DTSTAMP", "ATTENDEE", "DTSTART", "DTEND",
    }))
    output = _vevent_lines(reserialized, exclude=frozenset({
        "DTSTAMP", "ATTENDEE", "DTSTART", "DTEND",
    }))

    missing = original - output
    assert not missing, f"Properties manquantes apres re-serialisation : {missing}"

    # DTSTART et DTEND doivent etre re-serialises en UTC (car on a converti au parsing)
    output_lines = _vevent_lines(reserialized, exclude=frozenset())
    assert any("DTSTART:19980312T133000Z" in ln for ln in output_lines)
    assert any("DTEND:19980312T143000Z" in ln for ln in output_lines)


def test_roundtrip_example3_string(deserializer, serializer):
    event_a = deserializer.deserialize(ICAL_EXAMPLE_3)
    reserialized = serializer.serialize(event_a)

    original = _vevent_lines(ICAL_EXAMPLE_3, exclude=frozenset({"DTSTAMP", "ATTENDEE"}))
    output = _vevent_lines(reserialized, exclude=frozenset({"DTSTAMP", "ATTENDEE"}))

    missing = original - output
    assert not missing, f"Properties manquantes apres re-serialisation : {missing}"


# ==========================================================================
# Exemples non-VEVENT (VJOURNAL, VFREEBUSY) - pas de crash
# Ces composants ne sont pas supportes ; on verifie uniquement l'absence
# d'exception lors du cycle deserialise->serialise.
# ==========================================================================

def test_roundtrip_example4_vtodo(deserializer, serializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_4)
    assert event.component_type == ComponentType.TASK
    output = serializer.serialize(event)
    assert "BEGIN:VTODO" in output
    assert "SUMMARY:Submit Income Taxes" in output


def test_roundtrip_example5_no_crash(deserializer):
    with pytest.raises(RequestException):
        deserializer.deserialize(ICAL_EXAMPLE_5)


def test_roundtrip_example6_no_crash(deserializer):
    with pytest.raises(RequestException):
        deserializer.deserialize(ICAL_EXAMPLE_6)


# ==========================================================================
# Roundtrip sur des CalEvent construits en Python (serialize -> deserialize)
# ==========================================================================

def test_roundtrip_python_event_minimal(serializer, deserializer):
    original = CalEvent(
        uid="python-roundtrip@test.com",
        title="Python Event",
        date_start=datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 5, 10, 15, 30, 0, tzinfo=timezone.utc),
    )
    ical = serializer.serialize(original)
    parsed = deserializer.deserialize(ical)

    assert parsed.uid == original.uid
    assert parsed.title == original.title
    assert parsed.date_start == original.date_start
    assert parsed.date_end == original.date_end


def test_roundtrip_python_event_with_rrule(serializer, deserializer):
    rule = CalRecurrenceRule(
        frequency=RecurrenceFrequency.WEEKLY,
        by_day=["TU", "TH"],
        count=8,
    )
    original = CalEvent(
        uid="rrule-roundtrip@test.com",
        title="Bi-weekly standup",
        date_start=datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 2, 9, 30, 0, tzinfo=timezone.utc),
        recurrence_rule=rule,
        categories=["MEETING"],
        description="Daily standup recurrent.",
    )
    ical = serializer.serialize(original)
    parsed = deserializer.deserialize(ical)

    assert parsed.uid == original.uid
    assert parsed.recurrence_rule is not None
    assert parsed.recurrence_rule.frequency == RecurrenceFrequency.WEEKLY
    assert parsed.recurrence_rule.by_day == ["TU", "TH"]
    assert parsed.recurrence_rule.count == 8
    assert parsed.categories == ["MEETING"]
    assert parsed.description == "Daily standup recurrent."


def test_roundtrip_python_event_with_reminder(serializer, deserializer):
    original = CalEvent(
        uid="reminder-roundtrip@test.com",
        title="Event with reminder",
        date_start=datetime(2024, 3, 20, 10, 0, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 3, 20, 11, 0, 0, tzinfo=timezone.utc),
        reminders=[CalReminder(method=ReminderMethod.POPUP, minutes_before=10)],
    )
    ical = serializer.serialize(original)
    parsed = deserializer.deserialize(ical)

    assert len(parsed.reminders) == 1
    assert parsed.reminders[0].method == ReminderMethod.POPUP
    assert parsed.reminders[0].minutes_before == 10


def test_roundtrip_python_event_text_with_special_chars(serializer, deserializer):
    original = CalEvent(
        uid="special-roundtrip@test.com",
        title="Meeting; Planning, Review",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        description="Line 1\nLine 2\nBackslash: \\end",
        location="Room 42; Building A, Floor 3",
    )
    ical = serializer.serialize(original)
    parsed = deserializer.deserialize(ical)

    assert parsed.title == original.title
    assert parsed.description == original.description
    assert parsed.location == original.location
