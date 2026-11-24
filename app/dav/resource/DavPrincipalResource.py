from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavPath import DavPath
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavResource import DavResource
from app.dav.serializer.UserSerializerDavProps import UserSerializerDavProps
from app.manager.dav.protocol.DavProtocolConst import (
    CALDAV_CALENDAR_HOME_SET,
    CARDDAV_ADDRESSBOOK_HOME_SET,
    DAV_COLLECTION,
    DAV_PRINCIPAL,
    DAV_PRINCIPAL_URL,
)
from app.manager.dav.protocol.model.DavHrefs import DavHrefs

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavPrincipalResource(DavResource):
    """Principal of the account of the request (RFC 3744 section 2), locating its calendars and address books.

    It is also the collection holding the two homes.
    """

    def __init__(self, user: User, account_alias: str | None) -> None:
        super().__init__(
            path=DavPath.principal(user=user, account_alias=account_alias), user=user, account_alias=account_alias
        )

    def children(self) -> list[DavResource]:
        """Return the home of the calendars and the home of the address books."""
        return [
            DavCalendarHomeResource(user=self._user, account_alias=self._account_alias),
            DavAddressBookHomeResource(user=self._user, account_alias=self._account_alias),
        ]

    def _own_properties(self) -> dict[str, DavPropValue]:
        """Return the paths of the principal and of its homes, then the properties of the user. The paths are
        the ones of the account, with the alias of its login: a client following them stays on that account."""
        calendar_home: str = DavPath.calendar_home(user=self._user, account_alias=self._account_alias)
        addressbook_home: str = DavPath.addressbook_home(user=self._user, account_alias=self._account_alias)
        properties: dict[str, DavPropValue] = {
            DAV_PRINCIPAL_URL: DavHrefs(hrefs=(self.path,)),
            CALDAV_CALENDAR_HOME_SET: DavHrefs(hrefs=(calendar_home,)),
            CARDDAV_ADDRESSBOOK_HOME_SET: DavHrefs(hrefs=(addressbook_home,)),
        }
        properties.update(UserSerializerDavProps().serialize(self._user))
        return properties

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION, DAV_PRINCIPAL)
