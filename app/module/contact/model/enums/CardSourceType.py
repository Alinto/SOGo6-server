from __future__ import annotations

from enum import Enum


class CardSourceType(str, Enum):
    """Backend behind an address book (mirrors CalendarSourceType).

    'local'   - personal address book stored in the DB, full CRUD.
    'carddav' - read-write sync with a remote CardDAV server (RFC 6352).
    """
    UNDEFINED = "undefined"
    LOCAL = "local"
    CARDDAV = "carddav"
