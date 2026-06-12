"""Unit tests for InterfaceApiCalendarCalendar — calendar CRUD timezone defaulting and public subscription."""
from unittest.mock import MagicMock, patch

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.serializer.CalendarSerializerDict import CalendarSerializerDict
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _build_interface(user_tz="Europe/Paris"):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.user.mail = "alice@example.com"
    inter.module = MagicMock()
    # Return the calendar passed in so we can assert on what was built.
    inter.module.create_calendar.side_effect = lambda user, cal: cal
    inter._calendar_serializer = CalendarSerializerDict()
    inter._process_setting = MagicMock(SOGO_P_PUBLIC_BASE_URL="")
    inter._user_module = MagicMock()
    inter._user_module.get_partial_user_preferences.return_value = {"USER_GENERAL": {"SOGO_U_TIMEZONE": user_tz}}
    inter.settings = MagicMock(SOGO_D_CALENDAR_PUBLIC_LINK_ENABLED=True)
    return inter


def _created_calendar(inter) -> CalCalendar:
    return inter.module.create_calendar.call_args.args[1]


def test_create_calendar_defaults_to_user_timezone():
    inter = _build_interface(user_tz="Europe/Paris")
    inter.create_calendar({"name": "Work"})
    assert _created_calendar(inter).timezone == "Europe/Paris"


def test_create_calendar_keeps_explicit_timezone():
    inter = _build_interface(user_tz="Europe/Paris")
    inter.create_calendar({"name": "Work", "timezone": "America/New_York"})
    assert _created_calendar(inter).timezone == "America/New_York"


def test_create_calendar_empty_timezone_falls_back_to_user():
    inter = _build_interface(user_tz="Asia/Tokyo")
    inter.create_calendar({"name": "Work", "timezone": ""})
    assert _created_calendar(inter).timezone == "Asia/Tokyo"


# ========== new-event preferences ==========

def test_create_calendar_wires_preferences_and_converts_default_type():
    inter = _build_interface()
    inter.create_calendar({"name": "Work", "default_type": "private",
                           "default_event_duration_min": 45, "include_in_freebusy": False})
    cal = _created_calendar(inter)
    assert cal.default_type == EventVisibility.PRIVATE
    assert cal.default_event_duration_min == 45
    assert cal.include_in_freebusy is False


def test_create_calendar_default_type_absent_stays_none():
    inter = _build_interface()
    inter.create_calendar({"name": "Work"})
    assert _created_calendar(inter).default_type is None


def test_update_calendar_normalizes_default_type_to_enum():
    inter = _build_interface()
    inter.module.update_calendar.return_value = CalCalendar(key="k", user_uid="u", name="C")
    inter.update_calendar("k", {"default_type": "confidential"})
    updates = inter.module.update_calendar.call_args.args[2]
    assert updates["default_type"] == EventVisibility.CONFIDENTIAL


def test_update_calendar_default_type_null_clears():
    inter = _build_interface()
    inter.module.update_calendar.return_value = CalCalendar(key="k", user_uid="u", name="C")
    inter.update_calendar("k", {"default_type": None})
    updates = inter.module.update_calendar.call_args.args[2]
    assert updates["default_type"] is None


# ========== public subscription ==========

_FAKE_URL = "https://host/api/user/v1/public/calendars/tok123"


@patch("app.utils.api.external_url.url_for", return_value=_FAKE_URL)
def test_enable_subscription_returns_token_and_url(_url_for):
    inter = _build_interface()
    inter.module.enable_subscription.return_value = "tok123"
    response, _ = inter.enable_subscription("cal-key")
    assert response["error_code"] == "S000000"
    assert response["data"]["share_token"] == "tok123"
    assert response["data"]["public_url"] == _FAKE_URL


def test_enable_subscription_translates_error():
    inter = _build_interface()
    inter.module.enable_subscription.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    response, _ = inter.enable_subscription("cal-key")
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c
    assert response["data"] is None


def test_enable_subscription_translates_public_link_disabled():
    inter = _build_interface()
    inter.module.enable_subscription.side_effect = RequestException(error=err.ERROR_CALENDAR_PUBLIC_LINK_DISABLED)
    response, _ = inter.enable_subscription("cal-key")
    assert response["error_code"] == err.ERROR_CALENDAR_PUBLIC_LINK_DISABLED.c


@patch("app.utils.api.external_url.url_for", return_value=_FAKE_URL)
def test_disable_subscription_returns_calendar_without_url(_url_for):
    inter = _build_interface()
    cal = CalCalendar(key="cal-key", user_uid="alice@example.com", name="Cal", share_token=None)
    source = MagicMock()
    source.calendar = cal
    inter.module.get_calendar.return_value = source
    response, _ = inter.disable_subscription("cal-key")
    assert response["error_code"] == "S000000"
    assert response["data"]["public_url"] is None


def test_export_public_calendar_returns_text_calendar():
    inter = _build_interface()
    inter.module.get_calendar_by_share_token.return_value = MagicMock(user_uid="owner@example.com")
    inter._calendar_settings_by_uid = MagicMock(return_value=MagicMock())
    inter.module.export_by_share_token.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    body, status, headers = inter.export_public_calendar("tok123")
    assert status == 200
    assert body.startswith("BEGIN:VCALENDAR")
    assert headers["Content-Type"] == "text/calendar; charset=utf-8"
    # The domain settings handed to the export are the calendar OWNER's ones.
    inter._calendar_settings_by_uid.assert_called_once_with("owner@example.com")


def test_export_public_calendar_unknown_token_returns_error_envelope():
    inter = _build_interface()
    inter.module.get_calendar_by_share_token.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    response, _ = inter.export_public_calendar("bad")
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c
    assert response["data"] is None


@patch("app.utils.api.external_url.url_for", return_value=_FAKE_URL)
def test_get_calendar_includes_public_url_when_active(_url_for):
    inter = _build_interface()
    cal = CalCalendar(key="cal-key", user_uid="alice@example.com", name="Cal", share_token="tok123")
    source = MagicMock()
    source.calendar = cal
    inter.module.get_calendar.return_value = source
    response, _ = inter.get_calendar("cal-key")
    assert response["data"]["public_url"] == _FAKE_URL


def test_get_calendar_public_url_none_when_inactive():
    inter = _build_interface()
    cal = CalCalendar(key="cal-key", user_uid="alice@example.com", name="Cal", share_token=None)
    source = MagicMock()
    source.calendar = cal
    inter.module.get_calendar.return_value = source
    response, _ = inter.get_calendar("cal-key")
    assert response["data"]["public_url"] is None


@patch("app.utils.api.external_url.url_for", return_value="/api/user/v1/public/calendars/tok123")
def test_public_url_prefers_configured_base_url(_url_for):
    inter = _build_interface()
    inter._process_setting = MagicMock(SOGO_P_PUBLIC_BASE_URL="https://cal.example.com/")
    cal = CalCalendar(key="cal-key", user_uid="alice@example.com", name="Cal", share_token="tok123")
    source = MagicMock()
    source.calendar = cal
    inter.module.get_calendar.return_value = source
    response, _ = inter.get_calendar("cal-key")
    assert response["data"]["public_url"] == "https://cal.example.com/api/user/v1/public/calendars/tok123"
