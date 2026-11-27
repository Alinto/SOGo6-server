from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DavComponentSet:
    """Value of the supported-calendar-component-set property (RFC 4791 section 5.2.3).

    ``components`` holds the names of the calendar components a calendar holds, as "VEVENT".
    """

    components: tuple[str, ...]
