from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DavResourceType:
    """Value of the resourcetype property (RFC 4918 section 15.9).

    ``types`` holds the names, in Clark notation, of the types of the resource, as "{DAV:}collection". A
    resource that is not a collection, as a calendar object, has none.
    """

    types: tuple[str, ...] = ()
