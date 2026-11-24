from __future__ import annotations
from typing import TYPE_CHECKING, final

from abc import ABC, abstractmethod

from app.dav.DavPath import DavPath
from app.manager.dav.protocol.DavProtocolConst import DAV_CURRENT_USER_PRINCIPAL, DAV_RESOURCETYPE
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavResourceType import DavResourceType

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavResource(ABC):
    """Resource of the DAV tree of an account, with its properties and its members.

    ``path`` is the absolute path of the resource, not percent-encoded, ending with "/" for a collection.
    The account is the authenticated user and the alias of its login, None without alias (see DavPath).
    """

    def __init__(self, path: str, user: User, account_alias: str | None) -> None:
        self.path: str = path
        self._user: User = user
        self._account_alias: str | None = account_alias

    @final
    def properties(self) -> dict[str, DavPropValue]:
        """Return the properties of the resource, by name in Clark notation: the ones of every resource, then
        its own ones."""
        properties: dict[str, DavPropValue] = {
            DAV_RESOURCETYPE: DavResourceType(types=self._resource_types()),
            DAV_CURRENT_USER_PRINCIPAL: DavHrefs(
                hrefs=(DavPath.principal(user=self._user, account_alias=self._account_alias),)
            ),
        }
        properties.update(self._own_properties())
        return properties

    def children(self) -> list[DavResource]:
        """Return the members of the collection, listed by a PROPFIND with Depth 1."""
        return []

    def _own_properties(self) -> dict[str, DavPropValue]:
        """Return the properties specific to the resource."""
        return {}

    @abstractmethod
    def _resource_types(self) -> tuple[str, ...]:
        """Return the types of the resource, in Clark notation."""
