from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavPath import DavPath
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavResource import DavResource
from app.dav.serializer.UserSerializerDavProps import UserSerializerDavProps
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION, DAV_PRINCIPAL

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavPrincipalResource(DavResource):
    """Principal of the authenticated user (RFC 3744 section 2), locating its calendars and address books.

    It is also the collection holding the two homes.
    """

    def __init__(self, user: User) -> None:
        super().__init__(path=DavPath.principal(user), user=user)

    def children(self) -> list[DavResource]:
        """Return the home of the calendars and the home of the address books."""
        return [DavCalendarHomeResource(self._user), DavAddressBookHomeResource(self._user)]

    def _own_properties(self) -> dict[str, DavPropValue]:
        return UserSerializerDavProps().serialize(self._user)

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION, DAV_PRINCIPAL)
