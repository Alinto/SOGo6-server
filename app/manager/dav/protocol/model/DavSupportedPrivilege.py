from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DavSupportedPrivilege:
    """A privilege of a supported-privilege-set, with the privileges it aggregates (RFC 3744 section 5.3).

    ``privilege`` is the name of the privilege in Clark notation, as "{DAV:}read". ``description`` is the text
    shown to the user, in English (see DAV_DESCRIPTION_LANGUAGE). An ``abstract`` privilege cannot be granted alone.
    """

    privilege: str
    description: str
    abstract: bool = False
    contained: tuple[DavSupportedPrivilege, ...] = ()
