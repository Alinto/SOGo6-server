from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass

if TYPE_CHECKING:
    from app.manager.dav.protocol.model.DavSupportedPrivilege import DavSupportedPrivilege


@dataclass(frozen=True)
class DavSupportedPrivilegeSet:
    """Value of the supported-privilege-set property (RFC 3744 section 5.3): the tree of the privileges defined
    for the resource, from its top privileges."""

    privileges: tuple[DavSupportedPrivilege, ...]
