from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ROOT_PATH
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavResource import DavResource
from app.manager.dav.protocol.DavProtocolConst import DAV_COLLECTION

if TYPE_CHECKING:
    from app.auth.User import User


class DavRootResource(DavResource):
    """Root of the DAV tree. Its only member is the principal of the authenticated user: the other accounts
    are not listed."""

    def __init__(self, user: User) -> None:
        super().__init__(path=DAV_ROOT_PATH, user=user)

    def children(self) -> list[DavResource]:
        """Return the principal of the user."""
        return [DavPrincipalResource(self._user)]

    def _resource_types(self) -> tuple[str, ...]:
        return (DAV_COLLECTION,)
