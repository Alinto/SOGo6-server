"""Unit tests for IcsFetcher."""
from unittest.mock import patch

import pytest
import urllib.error

from app.module.calendar.sync.IcsFetcher import IcsFetcher
from app.utils.errors import ERROR_CALENDAR_ICS_FETCH_FAILED
from app.utils.exceptions import RequestException


def test_fetch_url_error():
    with patch("urllib.request.OpenerDirector.open", side_effect=urllib.error.URLError("connection refused")):
        with pytest.raises(RequestException) as exc_info:
            IcsFetcher.fetch("https://example.com/cal.ics")
    assert exc_info.value.error == ERROR_CALENDAR_ICS_FETCH_FAILED


def test_fetch_http_error():
    http_err = urllib.error.HTTPError(url=None, code=404, msg="Not Found", hdrs=None, fp=None)
    with patch("urllib.request.OpenerDirector.open", side_effect=http_err):
        with pytest.raises(RequestException) as exc_info:
            IcsFetcher.fetch("https://example.com/cal.ics")
    assert exc_info.value.error == ERROR_CALENDAR_ICS_FETCH_FAILED


def test_validate_rejects_ftp_scheme():
    with pytest.raises(RequestException):
        IcsFetcher._validate_url("ftp://example.com/cal.ics")


def test_validate_rejects_empty_hostname():
    with pytest.raises(RequestException):
        IcsFetcher._validate_url("https:///cal.ics")
