"""Unit tests for InterfaceApiCalendarCalendar - export_calendar and import_calendar."""
from unittest.mock import MagicMock

import pytest

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _build_interface(module=None):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.user.mail = "alice@example.com"
    inter.module = module if module is not None else MagicMock()
    inter._user_module = MagicMock()
    inter._user_module.get_partial_user_preferences.return_value = {"USER_GENERAL": {"SOGO_U_TIMEZONE": "UTC"}}
    return inter


# ========== export_calendar (async only) ==========

def test_export_enqueues_job_and_returns_job_id():
    module = MagicMock()
    module.export_calendar.return_value = "job-123"
    inter = _build_interface(module)
    body, status = inter.export_calendar("cal-key", {})
    assert status == 202
    assert body["data"]["job_id"] == "job-123"
    module.export_calendar.assert_called_once()


def test_export_forwards_date_bounds_to_module():
    module = MagicMock()
    module.export_calendar.return_value = "job-1"
    inter = _build_interface(module)
    inter.export_calendar("cal-key", {"start_date_time": "S", "end_date_time": "E"})
    kwargs = module.export_calendar.call_args.kwargs
    assert kwargs["date_start"] == "S"
    assert kwargs["date_end"] == "E"


def test_export_translates_request_exception_to_error_envelope():
    module = MagicMock()
    module.export_calendar.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.export_calendar("missing", {})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c
    assert response["data"] is None


# ========== import_calendar (async only) ==========

def test_import_enqueues_job_and_returns_job_id():
    module = MagicMock()
    module.import_calendar.return_value = "job-456"
    inter = _build_interface(module)
    body, status = inter.import_calendar("cal-key", "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    assert status == 202
    assert body["data"]["job_id"] == "job-456"


def test_import_forwards_text_to_module():
    module = MagicMock()
    module.import_calendar.return_value = "job-1"
    inter = _build_interface(module)
    ics_text = "BEGIN:VCALENDAR\r\nFOO:bar\r\nEND:VCALENDAR\r\n"
    inter.import_calendar("cal-key", ics_text)
    # The route already decoded the upload; the interface hands the text through.
    module.import_calendar.assert_called_once_with(inter.user, "cal-key", ics_text, is_async=True)


def test_import_translates_request_exception_to_error_envelope():
    module = MagicMock()
    module.import_calendar.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
    inter = _build_interface(module)
    response, _ = inter.import_calendar("cal-key", "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_SUPPORTED.c
    assert response["data"] is None
