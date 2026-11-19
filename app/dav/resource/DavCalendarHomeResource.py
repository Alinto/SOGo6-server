from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_CALENDAR_HOME
from app.dav.DavPath import DavPath
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION, DAV_DISPLAYNAME

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavCalendarHomeResource(DavResource):
    """Collection of the calendars of the user (RFC 4791 section 6.2.1)."""

    def __init__(self, user: User) -> None:
        super().__init__(path=DavPath.calendar_home(user), user=user)

    def _own_properties(self) -> dict[str, DavPropValue]:
        return {DAV_DISPLAYNAME: DAV_CALENDAR_HOME}

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION,)
