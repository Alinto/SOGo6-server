from __future__ import annotations

from enum import IntEnum


class ContactShareLevel(IntEnum):
    """Ordered access level for a shared address book.

    IntEnum values define the capability hierarchy: VIEW(1) < MODIFY(2). MODIFY grants read access
    plus write access (create / update / delete contacts), so comparisons like ``level >= MODIFY``
    work naturally.
    """

    VIEW = 1
    MODIFY = 2
