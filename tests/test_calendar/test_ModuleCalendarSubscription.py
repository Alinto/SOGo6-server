"""Unit tests for ModuleCalendar public subscription methods."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.CalendarConst import SHARE_TOKEN_LENGTH
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


class FakeSource(CalendarSource):
    def __init__(self, calendar, events=None):
        super().__init__(calendar)
        self._events = list(events or [])
        self.updated = False

    def _fetch_events(self, start, end, search=None):
        return list(self._events)

    def is_writable(self):
        return True

    def update_calendar(self, calendar):
        self.updated = True


def _fake_user(uid="alice@example.com"):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return user


def _make_source(events=None):
    cal = CalCalendar(key="cal-key", user_uid="alice@example.com", name="Cal", ctag=0, timezone="UTC")
    return FakeSource(cal, events=events)


def _build_module(source):
    module = object.__new__(ModuleCalendar)
    module._db = MagicMock()
    module._cache = MagicMock()
    module._acl = MagicMock()
    sources_mock = MagicMock()
    sources_mock.get_by_key.return_value = source
    module._sources = sources_mock
    module._imip = ImipProcessor(sources_mock)
    return module


def _settings(public_link_enabled=True):
    return MagicMock(SOGO_D_CALENDAR_PUBLIC_LINK_ENABLED=public_link_enabled)


# ========== enable_subscription ==========

def test_enable_subscription_sets_token_and_persists():
    source = _make_source()
    module = _build_module(source)
    token = module.enable_subscription(_fake_user(), "cal-key", _settings())
    assert len(token) == SHARE_TOKEN_LENGTH
    assert source.calendar.share_token == token
    assert source.updated is True


def test_enable_subscription_replaces_existing_token():
    source = _make_source()
    source.calendar.share_token = "old-token"
    module = _build_module(source)
    token = module.enable_subscription(_fake_user(), "cal-key", _settings())
    assert token != "old-token"
    assert len(token) == SHARE_TOKEN_LENGTH
    assert source.calendar.share_token == token


def test_enable_subscription_unknown_calendar_raises():
    module = _build_module(None)
    module._sources.get_by_key.return_value = None
    with pytest.raises(RequestException) as exc:
        module.enable_subscription(_fake_user(), "missing", _settings())
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_enable_subscription_refused_when_domain_disables_public_link():
    source = _make_source()
    module = _build_module(source)
    with pytest.raises(RequestException) as exc:
        module.enable_subscription(_fake_user(), "cal-key", _settings(public_link_enabled=False))
    assert exc.value.error == err.ERROR_CALENDAR_PUBLIC_LINK_DISABLED
    assert source.calendar.share_token is None
    assert source.updated is False


# ========== disable_subscription ==========

def test_disable_subscription_clears_token():
    source = _make_source()
    source.calendar.share_token = "some-token"
    module = _build_module(source)
    module.disable_subscription(_fake_user(), "cal-key")
    assert source.calendar.share_token is None
    assert source.updated is True


# Note: disable_subscription takes no domain settings on purpose - revoking an existing
# public link must stay possible even after the domain disables the feature.


# ========== export_by_share_token ==========

def test_get_calendar_by_share_token_returns_calendar():
    source = _make_source()
    source.calendar.share_token = "some-token"
    module = _build_module(source)
    module._sources.get_by_share_token.return_value = source
    calendar = module.get_calendar_by_share_token("some-token")
    assert calendar.user_uid == "alice@example.com"


def test_get_calendar_by_share_token_unknown_raises_not_found():
    module = _build_module(None)
    module._sources.get_by_share_token.return_value = None
    with pytest.raises(RequestException) as exc:
        module.get_calendar_by_share_token("bad-token")
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_export_by_share_token_returns_vcalendar():
    event = CalEvent(uid="pub@x", title="Pub", key="k1", date_start=_dt(2026, 7, 1, 9), date_end=_dt(2026, 7, 1, 10))
    source = _make_source(events=[event])
    module = _build_module(source)
    module._sources.get_by_share_token.return_value = source
    result = module.export_by_share_token("some-token", _settings())
    assert "BEGIN:VCALENDAR" in result
    assert "pub@x" in result


def test_export_by_share_token_unknown_raises_not_found():
    module = _build_module(None)
    module._sources.get_by_share_token.return_value = None
    with pytest.raises(RequestException) as exc:
        module.export_by_share_token("bad-token", _settings())
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_export_by_share_token_dead_when_owner_domain_disables_public_link():
    source = _make_source()
    source.calendar.share_token = "some-token"
    module = _build_module(source)
    module._sources.get_by_share_token.return_value = source
    with pytest.raises(RequestException) as exc:
        module.export_by_share_token("some-token", _settings(public_link_enabled=False))
    # Same 404 as an unknown token: a disabled domain must not reveal the token exists.
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND
