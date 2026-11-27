"""Unit tests for ModuleCalendar.get_all_owned_calendars - the calendars owned by a user."""

from unittest.mock import MagicMock

from app.auth.User import User
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.acl.CalendarAclEngine import CalendarAclEngine
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType


def _build_module():
    module = object.__new__(ModuleCalendar)
    module._sources = MagicMock()
    module._acl = CalendarAclEngine()
    return module


def _source(cal):
    source = MagicMock()
    source.calendar = cal
    return source


# ========== Tests for get_all_owned_calendars ==========


def test_get_all_owned_calendars():
    module = _build_module()
    cal = CalCalendar(user_uid="alice@example.com", name="Personal", key="cal-k", source_type=CalendarSourceType.LOCAL)
    module._sources.get_all_owned.return_value = [_source(cal)]
    assert module.get_all_owned_calendars(User("alice@example.com")) == [cal]
    assert cal.permissions == CalendarPermissions.owner()
    module._sources.get_all_owned.assert_called_once_with("alice@example.com")
    module._sources.get_all.assert_not_called()
