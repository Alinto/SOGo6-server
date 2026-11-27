from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_CALENDAR_HOME
from app.dav.DavPath import DavPath
from app.dav.resource.DavCalendarResource import DavCalendarResource
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION, DAV_DISPLAYNAME

if TYPE_CHECKING:
    from app.auth.User import User
    from app.interface.calendar.InterfaceDavCalendar import InterfaceDavCalendar
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavCalendarHomeResource(DavResource):
    """Collection of the calendars of the user (RFC 4791 section 6.2.1)."""

    def __init__(self, user: User, account_alias: str | None, calendar_interface: InterfaceDavCalendar) -> None:
        super().__init__(
            path=DavPath.calendar_home(user=user, account_alias=account_alias),
            user=user,
            account_alias=account_alias,
        )
        self._calendar_interface: InterfaceDavCalendar = calendar_interface

    def children(self) -> list[DavResource]:
        """Return the calendars of the user, each one under its name in the path."""
        return [
            DavCalendarResource(user=self._user, account_alias=self._account_alias, name=name, properties=properties)
            for name, properties in self._calendar_interface.get_all_calendars().items()
        ]

    def _own_properties(self) -> dict[str, DavPropValue]:
        return {DAV_DISPLAYNAME: DAV_CALENDAR_HOME}

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION,)
