from __future__ import annotations

from enum import Enum


class PropfindKind(Enum):
    """
    What a PROPFIND request asks (RFC 4918 section 9.1).
    """

    ALLPROP = "allprop"  # The properties of the resource, plus the ones of an include element
    PROPNAME = "propname"  # The names of the properties of the resource, without their value
    PROP = "prop"  # The listed properties
