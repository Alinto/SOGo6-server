"""
Tests unitaires pour CalendarEventSerializerIcal.
Verifie la conformite RFC 5545 des proprietes, de l'encodage TEXT et du folding.
"""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal


def _unfolded_lines(ical_text: str) -> list[str]:
    """Renvoie les content lines d'un texte iCal, apres unfolding et normalisation CRLF."""
    normalized = ical_text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded = re.sub(r"\n[ \t]", "", normalized)
    return [line for line in unfolded.splitlines() if line]


def _has_line(ical_text: str, line: str) -> bool:
    """Verifie qu'une content line exacte est presente apres unfolding."""
    return line in _unfolded_lines(ical_text)


@pytest.fixture
def serializer():
    """Fournit une instance fraiche du serialiseur."""
    return CalendarEventSerializerIcal()


@pytest.fixture
def minimal_event():
    """Evenement minimal avec seulement les champs obligatoires."""
    return CalEvent(
        uid="test-uid@example.com",
        title="Test Event",
        date_start=datetime(2024, 3, 15, 9, 0, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


# ==========================================================================
# Structure VCALENDAR / VEVENT
# ==========================================================================

def test_vcalendar_envelope(serializer, minimal_event):
    output = serializer.serialize(minimal_event)
    assert output.startswith("BEGIN:VCALENDAR\r\n")
    assert output.endswith("END:VCALENDAR\r\n")
    assert _has_line(output, "VERSION:2.0")
    assert _has_line(output, "CALSCALE:GREGORIAN")
    assert _has_line(output, "BEGIN:VEVENT")
    assert _has_line(output, "END:VEVENT")


def test_crlf_line_endings(serializer, minimal_event):
    output = serializer.serialize(minimal_event)
    # Chaque content line (avant folding) doit se terminer par CRLF
    assert "\r\n" in output
    # Pas de LF nu en dehors des continuations
    lines = output.split("\r\n")
    for line in lines[:-1]:  # last element is empty string after final CRLF
        assert "\n" not in line


def test_required_vevent_properties(serializer, minimal_event):
    output = serializer.serialize(minimal_event)
    assert _has_line(output, "UID:test-uid@example.com")
    assert _has_line(output, "SUMMARY:Test Event")
    assert _has_line(output, "DTSTART:20240315T090000Z")
    assert _has_line(output, "DTEND:20240315T100000Z")
    # DTSTAMP est obligatoire (RFC 5545 §3.6.1) — presence suffisante, valeur dynamique
    lines = _unfolded_lines(output)
    assert any(ln.startswith("DTSTAMP:") for ln in lines)


# ==========================================================================
# Proprietes optionnelles
# ==========================================================================

def test_optional_text_properties(serializer):
    event = CalEvent(
        uid="opt@test.com",
        title="With Optionals",
        date_start=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
        description="A description.",
        location="Room 101",
        url="https://example.com",
        sequence=3,
    )
    output = serializer.serialize(event)
    assert _has_line(output, "DESCRIPTION:A description.")
    assert _has_line(output, "LOCATION:Room 101")
    assert _has_line(output, "URL:https://example.com")
    assert _has_line(output, "SEQUENCE:3")


def test_status_and_visibility(serializer):
    event = CalEvent(
        uid="sv@test.com",
        title="Status Test",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        status=EventStatus.TENTATIVE,
        visibility=EventVisibility.PRIVATE,
        show_as=ShowAs.FREE,
    )
    output = serializer.serialize(event)
    assert _has_line(output, "STATUS:TENTATIVE")
    assert _has_line(output, "CLASS:PRIVATE")
    assert _has_line(output, "TRANSP:TRANSPARENT")


def test_show_as_out_of_office(serializer):
    event = CalEvent(
        uid="ooo@test.com",
        title="OOO",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        show_as=ShowAs.OUT_OF_OFFICE,
    )
    output = serializer.serialize(event)
    assert _has_line(output, "TRANSP:OPAQUE")
    assert _has_line(output, "X-MICROSOFT-CDO-BUSYSTATUS:OOF")


def test_categories(serializer):
    event = CalEvent(
        uid="cat@test.com",
        title="Categorized",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        categories=["MEETING", "PROJECT"],
    )
    output = serializer.serialize(event)
    assert _has_line(output, "CATEGORIES:MEETING,PROJECT")


# ==========================================================================
# Encodage TEXT (RFC 5545 §3.3.11)
# ==========================================================================

def test_text_escape_semicolon(serializer):
    event = CalEvent(
        uid="esc@test.com",
        title="Meeting; Planning",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )
    output = serializer.serialize(event)
    assert _has_line(output, r"SUMMARY:Meeting\; Planning")


def test_text_escape_comma(serializer):
    event = CalEvent(
        uid="esc@test.com",
        title="A, B",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )
    output = serializer.serialize(event)
    assert _has_line(output, r"SUMMARY:A\, B")


def test_text_escape_backslash(serializer):
    event = CalEvent(
        uid="esc@test.com",
        title=r"Path\to\file",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )
    output = serializer.serialize(event)
    assert _has_line(output, r"SUMMARY:Path\\to\\file")


def test_text_escape_newline_in_description(serializer):
    event = CalEvent(
        uid="esc@test.com",
        title="Event",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        description="Line 1\nLine 2",
    )
    output = serializer.serialize(event)
    # La newline dans la description doit etre encodee \n (et non pas un vrai CRLF)
    assert r"DESCRIPTION:Line 1\nLine 2" in "\n".join(_unfolded_lines(output))


# ==========================================================================
# Folding (RFC 5545 §3.1 — 75 octets max)
# ==========================================================================

def test_long_line_is_folded(serializer):
    long_title = "A" * 80  # SUMMARY: + 80 chars = 88 octets, doit etre foldee
    event = CalEvent(
        uid="fold@test.com",
        title=long_title,
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )
    output = serializer.serialize(event)
    raw_lines = output.split("\r\n")
    for line in raw_lines:
        assert len(line.encode("utf-8")) <= 75, f"Ligne trop longue ({len(line.encode())} octets) : {line!r}"


def test_folded_line_continuation_starts_with_space(serializer):
    long_title = "B" * 80
    event = CalEvent(
        uid="fold@test.com",
        title=long_title,
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )
    output = serializer.serialize(event)
    raw_lines = output.split("\r\n")
    # La premiere continuation doit commencer par un espace
    summary_idx = next(i for i, l in enumerate(raw_lines) if l.startswith("SUMMARY:"))
    assert raw_lines[summary_idx + 1].startswith(" ")


# ==========================================================================
# Evenement "all-day" (DATE value type)
# ==========================================================================

def test_allday_uses_date_format(serializer):
    event = CalEvent(
        uid="allday@test.com",
        title="Birthday",
        date_start=datetime(2024, 6, 15, tzinfo=timezone.utc),
        date_end=datetime(2024, 6, 16, tzinfo=timezone.utc),
        all_day=True,
    )
    output = serializer.serialize(event)
    assert _has_line(output, "DTSTART;VALUE=DATE:20240615")
    assert _has_line(output, "DTEND;VALUE=DATE:20240616")


# ==========================================================================
# Datetime avec TZID
# ==========================================================================

def test_tzid_datetime(serializer):
    event = CalEvent(
        uid="tz@test.com",
        title="Paris Meeting",
        date_start=datetime(2024, 3, 15, 9, 0, 0, tzinfo=ZoneInfo("Europe/Paris")),
        date_end=datetime(2024, 3, 15, 10, 0, 0, tzinfo=ZoneInfo("Europe/Paris")),
        timezone="Europe/Paris",
    )
    output = serializer.serialize(event)
    assert _has_line(output, "DTSTART;TZID=Europe/Paris:20240315T090000")
    assert _has_line(output, "DTEND;TZID=Europe/Paris:20240315T100000")


# ==========================================================================
# ORGANIZER
# ==========================================================================

def test_organizer_email_only(serializer):
    event = CalEvent(
        uid="org@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        organizer=CalOrganizer(email="boss@example.com"),
    )
    output = serializer.serialize(event)
    assert _has_line(output, "ORGANIZER:mailto:boss@example.com")


def test_organizer_with_cn(serializer):
    event = CalEvent(
        uid="org@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        organizer=CalOrganizer(email="boss@example.com", name="John Smith"),
    )
    output = serializer.serialize(event)
    lines = _unfolded_lines(output)
    # RFC 5545 §3.2 : les valeurs de parametres contenant des espaces sont quotees
    assert any("ORGANIZER" in ln and 'CN="John Smith"' in ln and "mailto:boss@example.com" in ln for ln in lines)


# ==========================================================================
# VTODO
# ==========================================================================

def test_vtodo_begin_vtodo(serializer):
    event = CalEvent(
        uid="task@test.com", title="My Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
    )
    output = serializer.serialize(event)
    assert "BEGIN:VTODO" in output
    assert "BEGIN:VEVENT" not in output


def test_vtodo_uses_due_not_dtend(serializer):
    event = CalEvent(
        uid="task@test.com", title="My Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
    )
    lines = _unfolded_lines(serializer.serialize(event))
    assert any(ln.startswith("DUE:") for ln in lines)
    assert not any(ln.startswith("DTEND:") for ln in lines)


def test_vtodo_status_needs_action(serializer):
    event = CalEvent(
        uid="task@test.com", title="My Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
        status=EventStatus.NEEDS_ACTION,
    )
    assert _has_line(serializer.serialize(event), "STATUS:NEEDS-ACTION")


def test_vtodo_status_completed(serializer):
    event = CalEvent(
        uid="task@test.com", title="Done Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
        status=EventStatus.COMPLETED,
    )
    assert _has_line(serializer.serialize(event), "STATUS:COMPLETED")


def test_vtodo_percent_complete(serializer):
    event = CalEvent(
        uid="task@test.com", title="Partial Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
        percent_complete=75,
    )
    assert _has_line(serializer.serialize(event), "PERCENT-COMPLETE:75")


def test_vtodo_percent_complete_absent_when_none(serializer):
    event = CalEvent(
        uid="task@test.com", title="Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
    )
    lines = _unfolded_lines(serializer.serialize(event))
    assert not any(ln.startswith("PERCENT-COMPLETE") for ln in lines)


def test_vtodo_completed_at(serializer):
    event = CalEvent(
        uid="task@test.com", title="Done Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
        completed_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    lines = _unfolded_lines(serializer.serialize(event))
    assert any(ln.startswith("COMPLETED:") for ln in lines)


def test_build_vcalendar_dispatches_vtodo_and_vevent(serializer):
    event = CalEvent(
        uid="evt@test.com", title="Event",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
    )
    task = CalEvent(
        uid="task@test.com", title="Task",
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        component_type=ComponentType.TASK,
    )
    output = serializer.build_vcalendar([event, task])
    assert "BEGIN:VEVENT" in output
    assert "BEGIN:VTODO" in output


# ==========================================================================
# ATTENDEE
# ==========================================================================

def test_attendee_basic(serializer):
    event = CalEvent(
        uid="att@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        attendees=[CalAttendee(email="alice@example.com", rsvp=True)],
    )
    output = serializer.serialize(event)
    lines = _unfolded_lines(output)
    assert any("ATTENDEE" in ln and "mailto:alice@example.com" in ln and "RSVP=TRUE" in ln for ln in lines)


def test_attendee_role_and_status(serializer):
    event = CalEvent(
        uid="att@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        attendees=[CalAttendee(
            email="bob@example.com",
            role=AttendeeRole.OPTIONAL,
            status=AttendeeStatus.ACCEPTED,
        )],
    )
    output = serializer.serialize(event)
    lines = _unfolded_lines(output)
    attendee_line = next(ln for ln in lines if "ATTENDEE" in ln and "mailto:bob@example.com" in ln)
    assert "ROLE=OPT-PARTICIPANT" in attendee_line
    assert "PARTSTAT=ACCEPTED" in attendee_line


# ==========================================================================
# RRULE
# ==========================================================================

def test_rrule_weekly_with_count(serializer):
    rule = CalRecurrenceRule(
        frequency=RecurrenceFrequency.WEEKLY,
        by_day=["MO", "WE"],
        count=5,
    )
    event = CalEvent(
        uid="rrule@test.com",
        title="Recurring",
        date_start=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        recurrence_rule=rule,
    )
    output = serializer.serialize(event)
    lines = _unfolded_lines(output)
    rrule_line = next(ln for ln in lines if ln.startswith("RRULE:"))
    assert "FREQ=WEEKLY" in rrule_line
    assert "BYDAY=MO,WE" in rrule_line
    assert "COUNT=5" in rrule_line


def test_rrule_monthly_with_until(serializer):
    rule = CalRecurrenceRule(
        frequency=RecurrenceFrequency.MONTHLY,
        by_month_day=[1],
        until=datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    event = CalEvent(
        uid="rrule@test.com",
        title="Monthly",
        date_start=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        recurrence_rule=rule,
    )
    output = serializer.serialize(event)
    lines = _unfolded_lines(output)
    rrule_line = next(ln for ln in lines if ln.startswith("RRULE:"))
    assert "FREQ=MONTHLY" in rrule_line
    assert "BYMONTHDAY=1" in rrule_line
    assert "UNTIL=20241231T235959Z" in rrule_line


# ==========================================================================
# VALARM
# ==========================================================================

def test_valarm_display(serializer):
    event = CalEvent(
        uid="alarm@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        reminders=[CalReminder(method=ReminderMethod.POPUP, minutes_before=15)],
    )
    output = serializer.serialize(event)
    assert _has_line(output, "BEGIN:VALARM")
    assert _has_line(output, "ACTION:DISPLAY")
    assert _has_line(output, "TRIGGER:-PT15M")
    assert _has_line(output, "END:VALARM")


def test_valarm_email(serializer):
    event = CalEvent(
        uid="alarm@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        reminders=[CalReminder(method=ReminderMethod.EMAIL, minutes_before=30)],
    )
    output = serializer.serialize(event)
    assert _has_line(output, "ACTION:EMAIL")
    assert _has_line(output, "TRIGGER:-PT30M")


# ==========================================================================
# ATTACH
# ==========================================================================

def test_attach_uri(serializer):
    event = CalEvent(
        uid="attach@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        attachments=[CalAttachment(
            url="https://example.com/doc.pdf",
            mime_type="application/pdf",
        )],
    )
    output = serializer.serialize(event)
    assert _has_line(output, "ATTACH;FMTTYPE=application/pdf:https://example.com/doc.pdf")


def test_attach_binary(serializer):
    event = CalEvent(
        uid="attach@test.com",
        title="Meeting",
        date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        attachments=[CalAttachment(data=b"hello", mime_type="text/plain")],
    )
    output = serializer.serialize(event)
    lines = _unfolded_lines(output)
    # icalendar trie les params alphabetiquement — on verifie chaque param independamment
    assert any("ATTACH" in ln and "ENCODING=BASE64" in ln and "VALUE=BINARY" in ln and "FMTTYPE=text/plain" in ln for ln in lines)
