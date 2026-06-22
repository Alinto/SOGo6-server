"""Unit tests for InterfaceApiCalendarCalendar - event CRUD methods."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.module.calendar.model.CalendarUser import CalendarUser

import pytest

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalEventDeserializerDict import CalEventDeserializerDict
from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict
from app.module.calendar.serializer.CalEventsSerializerDict import CalEventsSerializerDict
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc
_ICAL = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:REQUEST\r\nBEGIN:VEVENT\r\nUID:evt-1\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test",
        date_start=_dt(2026, 3, 1, 9),
        date_end=_dt(2026, 3, 1, 10),
        key="evt-key",
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_interface(module=None):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "user@example.com"
    inter.module = module if module is not None else MagicMock()
    inter._mail_outgoing = MagicMock()
    inter._event_serializer = CalEventSerializerDict()
    inter._event_deserializer = CalEventDeserializerDict()
    inter._events_serializer = CalEventsSerializerDict()
    return inter


# ========== create_event ==========

def test_create_event_success():
    event = _make_event()
    module = MagicMock()
    module.create_event.return_value = event
    inter = _build_interface(module)
    body = {
        "uid": "new@example.com",
        "title": "New event",
        "date_start": "2026-03-01T09:00:00.000Z",
        "date_end": "2026-03-01T10:00:00.000Z",
    }
    response, _ = inter.create_event("cal-key", body)
    assert response["error_code"] == "S000000"
    module.create_event.assert_called_once()


def test_create_event_returns_event_data():
    event = _make_event(title="Meeting")
    module = MagicMock()
    module.create_event.return_value = event
    inter = _build_interface(module)
    body = {
        "title": "Meeting",
        "date_start": "2026-03-01T09:00:00.000Z",
        "date_end": "2026-03-01T10:00:00.000Z",
    }
    response, _ = inter.create_event("cal-key", body)
    assert response["data"]["title"] == "Meeting"


def test_create_event_request_exception_returns_error():
    module = MagicMock()
    module.create_event.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    body = {"title": "T", "date_start": "2026-03-01T09:00:00.000Z", "date_end": "2026-03-01T10:00:00.000Z"}
    response, _ = inter.create_event("cal-key", body)
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c


def test_create_event_parse_error_returns_json_parse_failed():
    module = MagicMock()
    inter = _build_interface(module)
    body = {"title": "T", "date_start": "not-a-date", "date_end": "2026-03-01T10:00:00.000Z"}
    response, _ = inter.create_event("cal-key", body)
    assert response["error_code"] == err.ERROR_CALENDAR_JSON_PARSE_FAILED.c


def test_create_event_unexpected_exception_propagates():
    module = MagicMock()
    module.create_event.side_effect = RuntimeError("unexpected")
    inter = _build_interface(module)
    body = {"title": "T", "date_start": "2026-03-01T09:00:00.000Z", "date_end": "2026-03-01T10:00:00.000Z"}
    with pytest.raises(RuntimeError):
        inter.create_event("cal-key", body)


# ========== get_event ==========

def test_get_event_success():
    event = _make_event()
    module = MagicMock()
    module.get_event.return_value = event
    inter = _build_interface(module)
    response, _ = inter.get_event("evt-key")
    assert response["error_code"] == "S000000"
    assert response["data"]["uid"] == "evt@example.com"


def test_get_event_not_found():
    module = MagicMock()
    module.get_event.side_effect = RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.get_event("missing-key")
    assert response["error_code"] == err.ERROR_CALENDAR_EVENT_NOT_FOUND.c


# ========== patch_event ==========

def test_patch_event_applies_updates():
    existing = _make_event(title="Old title")
    updated = _make_event(title="Updated title")
    module = MagicMock()
    module.get_event.return_value = existing
    module.update_event.return_value = updated
    inter = _build_interface(module)
    response, _ = inter.patch_event("evt-key", {"title": "Updated title"})
    assert response["error_code"] == "S000000"
    assert response["data"]["title"] == "Updated title"


def test_patch_event_not_found_returns_error():
    module = MagicMock()
    module.get_event.side_effect = RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.patch_event("missing-key", {"title": "X"})
    assert response["error_code"] == err.ERROR_CALENDAR_EVENT_NOT_FOUND.c


# ========== delete_event ==========

def test_delete_event_success():
    module = MagicMock()
    inter = _build_interface(module)
    response, _ = inter.delete_event("evt-key")
    assert response["error_code"] == "S000000"
    assert response["data"] is None
    module.delete_event.assert_called_once_with(CalendarUser(user=inter.user, owner=inter.user), "evt-key")


def test_delete_event_not_found_returns_error():
    module = MagicMock()
    module.delete_event.side_effect = RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.delete_event("missing-key")
    assert response["error_code"] == err.ERROR_CALENDAR_EVENT_NOT_FOUND.c


def test_delete_event_unexpected_error_propagates():
    module = MagicMock()
    module.delete_event.side_effect = RuntimeError("boom")
    inter = _build_interface(module)
    with pytest.raises(RuntimeError):
        inter.delete_event("evt-key")


# ========== get_events ==========

def test_get_events_defaults_to_today_when_no_filters():
    event = _make_event()
    module = MagicMock()
    module.get_events.return_value = [event]
    inter = _build_interface(module)
    response, _ = inter.get_events("cal-key", {})
    assert response["error_code"] == "S000000"
    assert response["data"]["total_count"] == 1
    call_args = module.get_events.call_args
    start_arg = call_args[0][1]
    end_arg = call_args[0][2]
    assert start_arg is not None
    assert end_arg is not None


def test_get_events_passes_explicit_dates():
    event = _make_event()
    module = MagicMock()
    module.get_events.return_value = [event]
    inter = _build_interface(module)
    query = {"start_date_time": _dt(2026, 1, 1), "end_date_time": _dt(2026, 12, 31)}
    response, _ = inter.get_events("cal-key", query)
    assert response["error_code"] == "S000000"
    call_args = module.get_events.call_args
    assert call_args[0][1] == _dt(2026, 1, 1)
    assert call_args[0][2] == _dt(2026, 12, 31)


def test_get_events_error_returns_error():
    module = MagicMock()
    module.get_events.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.get_events("cal-key", {})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c


# ========== iMIP send on create_event ==========

_BUILD_REQUEST = "app.interface.calendar.InterfaceApiCalendarCalendar.ImipBuilder.build_request"
_BODY = {"title": "T", "date_start": "2026-03-01T09:00:00.000Z", "date_end": "2026-03-01T10:00:00.000Z"}


def _imip_message(recipients=("guest@example.com",)):
    event = _make_event(title="Invite")
    return ImipMessage(
        method=ImipMethod.REQUEST, event=event, from_email="org@example.com",
        to_emails=list(recipients), ical_content=_ICAL,
    )


def test_create_event_sends_imip_when_present():
    module = MagicMock()
    module.create_event.return_value = _make_event()
    inter = _build_interface(module)
    with patch(_BUILD_REQUEST, return_value=_imip_message()):
        response, code = inter.create_event("cal-key", _BODY)
    assert response["error_code"] == "S000000"
    assert code == 201
    inter._mail_outgoing.send_raw_message.assert_called_once()
    account_id, message = inter._mail_outgoing.send_raw_message.call_args.args
    assert account_id == "0"
    assert message["To"] == "guest@example.com"
    assert message["Subject"] == "Invitation: Invite"


def test_create_event_sends_one_mail_per_attendee():
    module = MagicMock()
    module.create_event.return_value = _make_event()
    inter = _build_interface(module)
    message = _imip_message(recipients=("a@example.com", "b@example.com"))
    with patch(_BUILD_REQUEST, return_value=message):
        inter.create_event("cal-key", _BODY)
    assert inter._mail_outgoing.send_raw_message.call_count == 2
    sent_to = {call.args[1]["To"] for call in inter._mail_outgoing.send_raw_message.call_args_list}
    assert sent_to == {"a@example.com", "b@example.com"}


def test_create_event_without_attendees_does_not_send():
    module = MagicMock()
    module.create_event.return_value = _make_event()
    inter = _build_interface(module)
    with patch(_BUILD_REQUEST, return_value=None):
        inter.create_event("cal-key", _BODY)
    inter._mail_outgoing.send_raw_message.assert_not_called()


def test_create_event_one_failed_recipient_does_not_block_others():
    module = MagicMock()
    module.create_event.return_value = _make_event()
    inter = _build_interface(module)
    inter._mail_outgoing.send_raw_message.side_effect = [RuntimeError("smtp down"), None]
    message = _imip_message(recipients=("a@example.com", "b@example.com"))
    with patch(_BUILD_REQUEST, return_value=message):
        response, code = inter.create_event("cal-key", _BODY)
    assert response["error_code"] == "S000000"
    assert code == 201
    assert inter._mail_outgoing.send_raw_message.call_count == 2
