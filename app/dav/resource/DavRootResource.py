from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ROOT_PATH
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION

if TYPE_CHECKING:
    from app.auth.User import User


class DavRootResource(DavResource):
    """Root of the DAV tree. Its only member is the principal of the account of the request: the other
    accounts are not listed."""

    def __init__(self, user: User, account_alias: str | None) -> None:
        super().__init__(path=DAV_ROOT_PATH, user=user, account_alias=account_alias)

    def children(self) -> list[DavResource]:
        """Return the principal of the account."""
        return [DavPrincipalResource(user=self._user, account_alias=self._account_alias)]

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION,)
