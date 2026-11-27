"""Unit tests for InterfaceDavCalendar - the module and the serializer of the properties are fakes."""

import pytest

from app.auth.User import User
from app.interface.calendar import InterfaceDavCalendar as interface_module
from app.interface.calendar.InterfaceDavCalendar import InterfaceDavCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.serializer.CalCalendarTimezoneSerializerIcal import CalCalendarTimezoneSerializerIcal

DISPLAYNAME = "{DAV:}displayname"
TIMEZONE = "{urn:ietf:params:xml:ns:caldav}calendar-timezone"
USER = User("alice@example.org", "secret")
DEFAULT = CalCalendar(
    user_uid="alice@example.org",
    name="Personal",
    key="k-default",
    is_default=True,
    source_type=CalendarSourceType.LOCAL,
)
ICS = CalCalendar(
    user_uid="alice@example.org",
    name="Holidays",
    key="k-ics",
    timezone="Europe/Paris",
    source_type=CalendarSourceType.ICS,
)


class FakeModuleCalendar:
    def __init__(self, calendars):
        self.calendars = calendars
        self.users = []

    def get_all_owned_calendars(self, user):
        self.users.append(user)
        return self.calendars


class FakeCalendarSerializer:
    def __init__(self):
        self.calendars = []

    def serialize(self, data):
        self.calendars.append(data)
        return {DISPLAYNAME: data.name}


@pytest.fixture
def interface(monkeypatch):
    module = FakeModuleCalendar([DEFAULT, ICS])
    monkeypatch.setattr(interface_module, "ModuleCalendar", lambda process_setting, cache: module)
    return InterfaceDavCalendar(
        process_setting=None,
        user=USER,
        cache=None,
        calendar_serializer=FakeCalendarSerializer(),
        default_calendar_name="personal",
    )


def _timezone(calendar):
    return CalCalendarTimezoneSerializerIcal().serialize(calendar)


# ========== Tests for get_all_calendars ==========


def test_get_all_calendars(interface):
    assert interface.get_all_calendars() == {
        "personal": {DISPLAYNAME: "Personal", TIMEZONE: _timezone(DEFAULT)},
        "k-ics": {DISPLAYNAME: "Holidays", TIMEZONE: _timezone(ICS)},
    }
    assert interface.module.users == [USER]


# ========== Tests for get_calendar ==========


@pytest.mark.parametrize("name, calendar", [("personal", DEFAULT), ("k-default", DEFAULT), ("k-ics", ICS)])
def test_get_calendar(interface, name, calendar):
    assert interface.get_calendar(name) == {DISPLAYNAME: calendar.name, TIMEZONE: _timezone(calendar)}
    assert interface._calendar_serializer.calendars == [calendar]


@pytest.mark.parametrize("name", ["unknown", "Personal"])
def test_get_calendar_unknown(interface, name):
    assert interface.get_calendar(name) is None
