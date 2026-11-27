from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ROOT_PATH
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION

if TYPE_CHECKING:
    from app.auth.User import User
    from app.interface.calendar.InterfaceDavCalendar import InterfaceDavCalendar


class DavRootResource(DavResource):
    """Root of the DAV tree. Its only member is the principal of the account of the request: the other
    accounts are not listed. It keeps the calendar interface to build the principal."""

    def __init__(self, user: User, account_alias: str | None, calendar_interface: InterfaceDavCalendar) -> None:
        super().__init__(path=DAV_ROOT_PATH, user=user, account_alias=account_alias)
        self._calendar_interface: InterfaceDavCalendar = calendar_interface

    def children(self) -> list[DavResource]:
        """Return the principal of the account."""
        return [
            DavPrincipalResource(
                user=self._user, account_alias=self._account_alias, calendar_interface=self._calendar_interface
            )
        ]

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION,)
