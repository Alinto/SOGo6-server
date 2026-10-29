"""Unit tests for ModuleCalendar.create_personal_calendar (first login provisioning)."""
from unittest.mock import MagicMock

from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType


def _calendar(user_uid="alice@example.com", is_default=True):
    return CalCalendar(user_uid=user_uid, name="Personal", key="cal-k",
                       is_default=is_default, source_type=CalendarSourceType.LOCAL)


def _fake_source(cal=None):
    source = MagicMock()
    source.calendar = cal or _calendar()
    return source


def _build_module():
    module = object.__new__(ModuleCalendar)
    module._db = MagicMock()
    module._sources = MagicMock()
    return module


def test_create_personal_calendar_returns_existing_default():
    module = _build_module()
    existing = _fake_source()
    module._sources.get_default.return_value = existing
    result = module.create_personal_calendar("alice@example.com")
    assert result is existing.calendar
    module._sources.get_default.assert_called_once_with("alice@example.com")
    module._sources.get.assert_not_called()


def test_create_personal_calendar_ignores_shared_default():
    """A default calendar shared by another user must not prevent provisioning."""
    module = _build_module()
    module._sources.get_all.return_value = [_fake_source(_calendar(user_uid="bob@example.com"))]
    module._sources.get_default.return_value = None
    new_source = _fake_source()
    new_source.save_calendar.side_effect = lambda cal: cal
    module._sources.get.return_value = new_source
    result = module.create_personal_calendar("alice@example.com", tz="Europe/Paris")
    assert result.user_uid == "alice@example.com"
    assert result.is_default is True
    assert result.timezone == "Europe/Paris"
    assert result.key
    new_source.save_calendar.assert_called_once()
