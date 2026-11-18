from __future__ import annotations

from dataclasses import dataclass, field

from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavResourceType import DavResourceType

# Value of a property: the text of a text property, or a value written as child elements
DavPropValue = str | DavHrefs | DavResourceType


@dataclass(frozen=True)
class DavPropResponse:
    """Properties of one resource in a multistatus response (RFC 4918 section 9.1).

    ``href`` is the path of the resource, not percent-encoded. ``found`` maps the names, in Clark notation,
    of the properties answered 200 to their value. ``missing`` holds the names of the asked properties the
    resource does not have, answered 404.
    """

    href: str
    found: dict[str, DavPropValue] = field(default_factory=dict)
    missing: tuple[str, ...] = ()
