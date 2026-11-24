from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ADDRESSBOOK_HOME
from app.dav.DavPath import DavPath
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION, DAV_DISPLAYNAME

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavAddressBookHomeResource(DavResource):
    """Collection of the address books of the user (RFC 6352 section 7.1.1)."""

    def __init__(self, user: User, account_alias: str | None) -> None:
        super().__init__(
            path=DavPath.addressbook_home(user=user, account_alias=account_alias),
            user=user,
            account_alias=account_alias,
        )

    def _own_properties(self) -> dict[str, DavPropValue]:
        return {DAV_DISPLAYNAME: DAV_ADDRESSBOOK_HOME}

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION,)
