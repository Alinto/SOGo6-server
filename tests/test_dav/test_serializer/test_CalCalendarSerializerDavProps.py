"""Unit tests for CalCalendarSerializerDavProps."""

from app.dav.serializer.CalCalendarSerializerDavProps import CalCalendarSerializerDavProps
from app.manager.dav.protocol.model.DavComponentSet import DavComponentSet
from app.module.calendar.model.CalCalendar import CalCalendar

# ========== Tests for serialize ==========


def test_serialize():
    calendar = CalCalendar(
        user_uid="alice@example.org", name="Work", key="k-work", ctag=7, color="#3a87ad", description="Team"
    )
    assert CalCalendarSerializerDavProps().serialize(calendar) == {
        "{DAV:}displayname": "Work",
        "{http://calendarserver.org/ns/}getctag": "7",
        "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set": DavComponentSet(
            components=("VEVENT", "VTODO")
        ),
        "{http://apple.com/ns/ical/}calendar-color": "#3a87ad",
        "{urn:ietf:params:xml:ns:caldav}calendar-description": "Team",
    }


def test_serialize_without_color_and_description():
    properties = CalCalendarSerializerDavProps().serialize(CalCalendar(user_uid="alice@example.org", name="Work"))
    assert "{http://apple.com/ns/ical/}calendar-color" not in properties
    assert "{urn:ietf:params:xml:ns:caldav}calendar-description" not in properties
