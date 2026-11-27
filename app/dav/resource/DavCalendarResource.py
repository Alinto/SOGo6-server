from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavPath import DavPath
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import (
    CALDAV_CALENDAR,
    CALDAV_READ_FREE_BUSY,
    DAV_COLLECTION,
    DAV_CURRENT_USER_PRIVILEGE_SET,
    DAV_READ,
    DAV_SUPPORTED_PRIVILEGE_SET,
)
from app.manager.dav.protocol.model.DavPrivilegeSet import DavPrivilegeSet
from app.manager.dav.protocol.model.DavSupportedPrivilege import DavSupportedPrivilege
from app.manager.dav.protocol.model.DavSupportedPrivilegeSet import DavSupportedPrivilegeSet

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavCalendarResource(DavResource):
    """Calendar collection of the user (RFC 4791 section 4.2), read only.

    ``name`` is the segment of the calendar in the path (see DavPath): a request naming the default calendar by
    its key instead of "personal" gets the path it asked for. ``properties`` are the ones of the calendar, as
    InterfaceDavCalendar gives them.
    """

    # Privileges defined on a calendar, all granted to the user: reading, which aggregates the reading of the free
    # busy time (RFC 3744 section 5.3, RFC 4791 section 6.1.1). Writing comes with the writing of the calendars.
    _SUPPORTED_PRIVILEGES: DavSupportedPrivilegeSet = DavSupportedPrivilegeSet(
        privileges=(
            DavSupportedPrivilege(
                privilege=DAV_READ,
                description="Read the calendar and its objects",
                contained=(
                    DavSupportedPrivilege(privilege=CALDAV_READ_FREE_BUSY, description="Read the free busy time"),
                ),
            ),
        )
    )
    # An aggregate privilege is listed with the privileges it holds (RFC 3744 section 5.4)
    _USER_PRIVILEGES: DavPrivilegeSet = DavPrivilegeSet(privileges=(DAV_READ, CALDAV_READ_FREE_BUSY))

    def __init__(self, user: User, account_alias: str | None, name: str, properties: dict[str, DavPropValue]) -> None:
        super().__init__(
            path=DavPath.calendar(user=user, account_alias=account_alias, name=name),
            user=user,
            account_alias=account_alias,
        )
        self._properties: dict[str, DavPropValue] = properties

    def _own_properties(self) -> dict[str, DavPropValue]:
        """Return the properties of the calendar, then the privileges: reading only, so that clients show the
        calendar read only."""
        properties: dict[str, DavPropValue] = dict(self._properties)
        properties[DAV_SUPPORTED_PRIVILEGE_SET] = DavCalendarResource._SUPPORTED_PRIVILEGES
        properties[DAV_CURRENT_USER_PRIVILEGE_SET] = DavCalendarResource._USER_PRIVILEGES
        return properties

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION, CALDAV_CALENDAR)
