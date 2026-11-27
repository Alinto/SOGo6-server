from app.dav.DavConst import DAV_CALENDAR_COMPONENTS
from app.manager.dav.protocol.DavProtocolConst import (
    APPLE_ICAL_CALENDAR_COLOR,
    CALDAV_CALENDAR_DESCRIPTION,
    CALDAV_SUPPORTED_CALENDAR_COMPONENT_SET,
    CALENDARSERVER_GETCTAG,
    DAV_DISPLAYNAME,
)
from app.manager.dav.protocol.model.DavComponentSet import DavComponentSet
from app.manager.dav.protocol.model.DavPropResponse import DavPropValue
from app.module.calendar.model.CalCalendar import CalCalendar
from app.utils.serializer.Serializer import Serializer


class CalCalendarSerializerDavProps(Serializer[CalCalendar, dict[str, DavPropValue]]):
    """Convert a calendar into the properties of its collection, by name in Clark notation. DavCalendarResource adds
    the path and the privileges, which depend on the request, and the time zone, written by the calendar module."""

    def serialize(self, data: CalCalendar) -> dict[str, DavPropValue]:
        """Return the name, the change tag and the components of the calendar, then its color and its
        description when it has them."""
        properties: dict[str, DavPropValue] = {
            DAV_DISPLAYNAME: data.name,
            # Changes with every object of the calendar: clients compare it before syncing the calendar
            CALENDARSERVER_GETCTAG: str(data.ctag),
            CALDAV_SUPPORTED_CALENDAR_COMPONENT_SET: DavComponentSet(components=DAV_CALENDAR_COMPONENTS),
        }
        if data.color:
            properties[APPLE_ICAL_CALENDAR_COLOR] = data.color
        if data.description:
            properties[CALDAV_CALENDAR_DESCRIPTION] = data.description
        return properties
