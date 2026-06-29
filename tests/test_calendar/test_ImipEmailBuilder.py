"""Unit tests for ImipEmailBuilder (ImipMessage -> RFC 6047 email)."""
from app.module.calendar.imip.ImipEmailBuilder import ImipEmailBuilder
from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.model.CalEvent import CalEvent

_ICAL = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:REQUEST\r\nBEGIN:VEVENT\r\nUID:evt-1\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"


def _msg(method=ImipMethod.REQUEST, title="Team sync"):
    event = CalEvent(title=title, uid="evt-1")
    return ImipMessage(
        method=method, event=event, from_email="org@example.org",
        to_emails=["a@example.org", "b@example.org"], ical_content=_ICAL,
    )


def test_headers():
    email = ImipEmailBuilder.build_email(_msg())
    assert email["From"] == "org@example.org"
    assert email["To"] == "a@example.org, b@example.org"
    assert email["Subject"] == "Invitation: Team sync"


def test_body_carries_method_and_ical():
    email = ImipEmailBuilder.build_email(_msg())
    assert email.get_content_type() == "text/calendar"
    assert email.get_param("method") == "REQUEST"
    assert email.get_param("component") == "VEVENT"
    assert "BEGIN:VCALENDAR" in email.get_content()


def test_body_is_calendar_only():
    email = ImipEmailBuilder.build_email(_msg())
    assert not email.is_multipart()
    assert email.get_content_type() == "text/calendar"


def test_subject_prefix_per_method():
    assert ImipEmailBuilder.build_email(_msg(ImipMethod.CANCEL))["Subject"] == "Cancelled: Team sync"
    assert ImipEmailBuilder.build_email(_msg(ImipMethod.REPLY))["Subject"] == "Re: Team sync"


def test_subject_falls_back_to_uid_without_title():
    assert ImipEmailBuilder.build_email(_msg(title=None))["Subject"] == "Invitation: evt-1"
