from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DavHrefs:
    """Value of a property referencing resources, as calendar-home-set or calendar-user-address-set.

    ``hrefs`` holds paths or URIs (mailto), not percent-encoded.
    """

    hrefs: tuple[str, ...]
