"""Calendar interface of the DAV server.

Like ``InterfaceAgentCalendar``: no Flask context, no HTTP response formatting. The ``RequestException`` of the
module goes up to the DAV dispatcher, which answers its HTTP status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.manager.dav.protocol.DavProtocolConst import CALDAV_CALENDAR_TIMEZONE
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.serializer.CalCalendarTimezoneSerializerIcal import CalCalendarTimezoneSerializerIcal

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.utils.serializer.Serializer import Serializer


class InterfaceDavCalendar:
    """Calendars of the user of a DAV request, as the properties of their collections."""

    def __init__(
        self,
        process_setting: ProcessSetting,
        user: User,
        cache: ClientRedis,
        calendar_serializer: Serializer[CalCalendar, dict[str, DavPropValue]],
        default_calendar_name: str,
    ) -> None:
        """The choices of the DAV server are given by DavResourceResolver, so that the interface does not depend on
        it: ``calendar_serializer`` converts a calendar into the properties of its collection
        (CalCalendarSerializerDavProps), ``default_calendar_name`` is the name of the default calendar in the paths.
        """
        self.user: User = user
        self.module: ModuleCalendar = ModuleCalendar(process_setting, cache=cache)
        self._calendar_serializer: Serializer[CalCalendar, dict[str, DavPropValue]] = calendar_serializer
        self._timezone_serializer: CalCalendarTimezoneSerializerIcal = CalCalendarTimezoneSerializerIcal()
        self._default_calendar_name: str = default_calendar_name

    def get_all_calendars(self) -> dict[str, dict[str, DavPropValue]]:
        """Return the properties of the calendars owned by the user, whatever their source, by name in the path.
        The calendars shared with the user are not listed: a shared default calendar would take the name of the
        default calendar of the user."""
        return {
            self._calendar_name(calendar): self._properties(calendar)
            for calendar in self.module.get_all_owned_calendars(self.user)
        }

    def get_calendar(self, name: str) -> dict[str, DavPropValue] | None:
        """Return the properties of a calendar listed by get_all_calendars, from its name in the path, or None. The
        default calendar is also found by its key. The name is case-sensitive."""
        for calendar in self.module.get_all_owned_calendars(self.user):
            if name in (self._calendar_name(calendar), calendar.key):
                return self._properties(calendar)
        return None

    def _calendar_name(self, calendar: CalCalendar) -> str:
        """Return the name of a calendar in its path: the default name for the default calendar, its key otherwise."""
        if calendar.is_default:
            return self._default_calendar_name
        return calendar.require_key

    def _properties(self, calendar: CalCalendar) -> dict[str, DavPropValue]:
        """Return the properties of the collection of a calendar, with its time zone written in iCalendar by the
        calendar module."""
        properties: dict[str, DavPropValue] = self._calendar_serializer.serialize(calendar)
        properties[CALDAV_CALENDAR_TIMEZONE] = self._timezone_serializer.serialize(calendar)
        return properties
