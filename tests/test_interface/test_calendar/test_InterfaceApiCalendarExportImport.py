"""Unit tests for InterfaceApiCalendarCalendar — export_calendar and import_calendar."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalSyncResult import CalSyncResult
from app.module.calendar.serializer.SyncResultSerializerDict import SyncResultSerializerDict
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _build_interface(module=None):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.user.mail = "alice@example.com"
    inter.module = module if module is not None else MagicMock()
    inter._sync_result_serializer = SyncResultSerializerDict()
    inter._user_module = MagicMock()
    inter._user_module.get_partial_user_preferences.return_value = {"USER_GENERAL": {"SOGO_U_TIMEZONE": "UTC"}}
    return inter


# ========== export_calendar ==========

def test_export_returns_inline_text_by_default():
    module = MagicMock()
    module.export_calendar.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    inter = _build_interface(module)
    body, status, headers = inter.export_calendar("cal-key", {})
    assert status == 200
    assert body.startswith("BEGIN:VCALENDAR")
    assert headers["Content-Type"] == "text/calendar; charset=utf-8"
    assert "Content-Disposition" not in headers


def test_export_with_download_true_adds_attachment_header():
    module = MagicMock()
    module.export_calendar.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    inter = _build_interface(module)
    body, status, headers = inter.export_calendar("cal-key", {"download": True})
    assert status == 200
    assert "attachment" in headers["Content-Disposition"]
    assert "cal-key" in headers["Content-Disposition"]


def test_export_forwards_date_range_query_arguments():
    module = MagicMock()
    module.export_calendar.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    inter = _build_interface(module)
    date_start = datetime(2026, 1, 1, tzinfo=_UTC)
    date_end = datetime(2026, 12, 31, tzinfo=_UTC)
    inter.export_calendar("cal-key", {"start_date_time": date_start, "end_date_time": date_end})
    module.export_calendar.assert_called_once_with(inter.user, "cal-key", date_start=date_start, date_end=date_end)


def test_export_without_date_range_passes_none():
    module = MagicMock()
    module.export_calendar.return_value = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    inter = _build_interface(module)
    inter.export_calendar("cal-key", {})
    module.export_calendar.assert_called_once_with(inter.user, "cal-key", date_start=None, date_end=None)


def test_export_translates_request_exception_to_error_envelope():
    module = MagicMock()
    module.export_calendar.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.export_calendar("missing", {})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c
    assert response["data"] is None


# ========== import_calendar ==========

def test_import_returns_sync_result_envelope():
    module = MagicMock()
    module.import_calendar.return_value = CalSyncResult(inserted=2, updated=1, deleted=0, total=3)
    inter = _build_interface(module)
    response, _ = inter.import_calendar("cal-key", "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    assert response["error_code"] == "S000000"
    assert response["data"]["inserted"] == 2
    assert response["data"]["updated"] == 1


def test_import_forwards_ics_text_unchanged():
    module = MagicMock()
    module.import_calendar.return_value = CalSyncResult(inserted=0, updated=0, deleted=0, total=0)
    inter = _build_interface(module)
    ics = "BEGIN:VCALENDAR\r\nFOO:bar\r\nEND:VCALENDAR\r\n"
    inter.import_calendar("cal-key", ics)
    # Timezone fallback is resolved in the module (from the calendar), not in the interface.
    module.import_calendar.assert_called_once_with(inter.user, "cal-key", ics)


def test_import_translates_request_exception_to_error_envelope():
    module = MagicMock()
    module.import_calendar.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
    inter = _build_interface(module)
    response, _ = inter.import_calendar("cal-key", "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_SUPPORTED.c
    assert response["data"] is None
