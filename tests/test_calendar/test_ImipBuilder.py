"""Unit tests for ImipBuilder."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.module.calendar.imip.ImipBuilder import ImipBuilder
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalendarUser import CalendarUser
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus


_UTC = timezone.utc


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Meeting",
        date_start=datetime(2026, 6, 1, 9, tzinfo=_UTC),
        date_end=datetime(2026, 6, 1, 10, tzinfo=_UTC),
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _organizer(email="alice@example.com"):
    return CalOrganizer(email=email, name="Alice")


def _attendee(email="bob@example.com", status=AttendeeStatus.NEEDS_ACTION):
    return CalAttendee(email=email, name="Bob", status=status)


def _fake_user(uid="bob@example.com"):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return CalendarUser(user=user, owner=user)


# ========== Tests for ImipBuilder.build_request ==========

def test_build_request_returns_message():
    event = _make_event(organizer=_organizer(), attendees=[_attendee()])
    msg = ImipBuilder.build_request(event)
    assert msg is not None
    assert msg.method == ImipMethod.REQUEST
    assert msg.from_email == "alice@example.com"
    assert "bob@example.com" in msg.to_emails
    assert "METHOD:REQUEST" in msg.ical_content


def test_build_request_no_organizer_returns_none():
    event = _make_event(attendees=[_attendee()])
    assert ImipBuilder.build_request(event) is None


def test_build_request_no_attendees_returns_none():
    event = _make_event(organizer=_organizer())
    assert ImipBuilder.build_request(event) is None


def test_build_request_multiple_attendees_all_in_to():
    attendees = [_attendee("b@x.com"), _attendee("c@x.com")]
    event = _make_event(organizer=_organizer(), attendees=attendees)
    msg = ImipBuilder.build_request(event)
    assert set(msg.to_emails) == {"b@x.com", "c@x.com"}


# ========== Tests for ImipBuilder.build_cancel ==========

def test_build_cancel_returns_message():
    event = _make_event(organizer=_organizer(), attendees=[_attendee()])
    msg = ImipBuilder.build_cancel(event)
    assert msg is not None
    assert msg.method == ImipMethod.CANCEL
    assert "METHOD:CANCEL" in msg.ical_content


def test_build_cancel_no_organizer_returns_none():
    event = _make_event(attendees=[_attendee()])
    assert ImipBuilder.build_cancel(event) is None


def test_build_cancel_occurrence_includes_recurrence_id():
    recid = datetime(2026, 6, 8, 9, tzinfo=_UTC)
    event = _make_event(
        organizer=_organizer(),
        attendees=[_attendee()],
        recurrence_id=recid,
    )
    msg = ImipBuilder.build_cancel(event)
    assert msg is not None
    assert "RECURRENCE-ID" in msg.ical_content


# ========== Tests for ImipBuilder.build_reply ==========

def test_build_reply_matching_attendee():
    attendee = _attendee("bob@example.com", AttendeeStatus.ACCEPTED)
    event = _make_event(organizer=_organizer("alice@example.com"), attendees=[attendee])
    msg = ImipBuilder.build_reply(event, _fake_user("bob@example.com"))
    assert msg is not None
    assert msg.method == ImipMethod.REPLY
    assert msg.from_email == "bob@example.com"
    assert msg.to_emails == ["alice@example.com"]
    # REPLY must contain only the replying attendee, not the full attendee list
    assert "METHOD:REPLY" in msg.ical_content


def test_build_reply_not_attendee_returns_none():
    event = _make_event(organizer=_organizer(), attendees=[_attendee("bob@example.com")])
    assert ImipBuilder.build_reply(event, _fake_user("carol@example.com")) is None


def test_build_reply_no_organizer_returns_none():
    event = _make_event(attendees=[_attendee("bob@example.com")])
    assert ImipBuilder.build_reply(event, _fake_user("bob@example.com")) is None


def test_build_reply_organizer_replying_to_self_returns_none():
    event = _make_event(organizer=_organizer("alice@example.com"), attendees=[_attendee("alice@example.com")])
    assert ImipBuilder.build_reply(event, _fake_user("alice@example.com")) is None


def test_build_reply_delegated_replies_for_owner_not_acting_user():
    # A delegate (carol) responds on the owner (bob)'s calendar - bob is the invitee.
    owner = MagicMock(uid="bob@example.com", mail="bob@example.com")
    actor = MagicMock(uid="carol@example.com", mail="carol@example.com")
    event = _make_event(
        organizer=_organizer("alice@example.com"),
        attendees=[_attendee("bob@example.com", AttendeeStatus.ACCEPTED)],
    )
    msg = ImipBuilder.build_reply(event, CalendarUser(user=actor, owner=owner))
    assert msg is not None
    assert msg.from_email == "bob@example.com"      # the owner (invitee), not the acting delegate
    assert msg.to_emails == ["alice@example.com"]
