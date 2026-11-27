from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DavPrivilegeSet:
    """Value of the current-user-privilege-set property (RFC 3744 section 5.4).

    ``privileges`` holds the names, in Clark notation, of the privileges of the user on the resource, as
    "{DAV:}read".
    """

    privileges: tuple[str, ...]
