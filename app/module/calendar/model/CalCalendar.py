from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType


@dataclass
class CalCalendar:  # pylint: disable=too-many-instance-attributes,invalid-name
    """
    Format-agnostic representation of a calendar (RFC 4791 §4.2 calendar collection).

    Maps to sogo_calendar_calendars. id is the internal integer PK; key is the opaque
    public identifier exposed in the API (prevents row enumeration).

    source_type drives CalendarSources dispatch:
      'local'  — personal calendar stored in DB, full CRUD
      'ics'    — read-only subscription to a remote .ics URL (RFC 5545 / WebDAV)
      'caldav' — read-write sync with a remote CalDAV server (RFC 4791)

    External sync metadata (URL, credentials, etag, last_sync) lives in sync_config JSON.
    prodid, calscale, method are VCALENDAR-level properties not stored in DB — populated
    only when building from an ICS source (import/export).
    """
    # Internal — owner's uid, FK to sogo_user_profiles.uid
    user_uid: str
    # RFC 4791 §5.2.1 — display name of the calendar collection (DAV:displayname)
    name: str

    # Internal — database auto-increment PK
    id: int | None = None
    # Internal — opaque token exposed in the API (see generate_uuid)
    key: str | None = None
    # RFC 7986 §5.9 COLOR — hex color #RRGGBB for UI display
    color: str | None = None
    # RFC 4791 §5.2.1 — free-text description (DAV:comment or CALDAV:calendar-description)
    description: str | None = None
    # RFC 5545 §3.2.19 TZID — default IANA timezone for new events (e.g. "Europe/Paris")
    timezone: str = "UTC"
    # Internal — marks the user's primary personal calendar; uniqueness enforced by service layer
    is_default: bool = False
    # Internal — discriminates calendar backend: local, ics, caldav
    source_type: CalendarSourceType = CalendarSourceType.UNDEFINED
    # CalDAV CS:getctag extension (draft-daboo-caldav-extensions) — opaque token incremented
    # by the service layer on every event mutation (insert / update / delete).
    # CalDAV clients compare it against their cached value to detect changes without
    # fetching the full event list — avoids unnecessary sync traffic.
    ctag: int = 0
    # Internal — opaque token for the public .ics subscription URL.
    # Stored as a relational column (not in JSON) because it is queried directly:
    # WHERE share_token = ?
    share_token: str | None = None
    # External sync metadata — NULL for source_type='local'.
    # Schema: {url, username, password (AES-encrypted), etag, last_sync,
    #          sync_interval_minutes}
    sync_config: dict | None = None

    # RFC 5545 §3.7.3 PRODID — identifies the product that created the VCALENDAR object
    prodid: str | None = None
    # RFC 5545 §3.7.1 CALSCALE — calendar scale, almost always "GREGORIAN"
    calscale: str | None = None
    # RFC 5546 §2.1.4 METHOD — iTIP method (REQUEST, REPLY, CANCEL…) for iMIP messages
    method: str | None = None
    # Catch-all for non-standard VCALENDAR-level X-* properties
    extra_properties: dict[str, str] = field(default_factory=dict)

    created_at: datetime | None = None
    updated_at: datetime | None = None

    MUTABLE_FIELDS: frozenset[str] = frozenset({"name", "color", "description", "timezone", "is_default", "sync_config"})

    def apply_update(self, updates: dict[str, Any]) -> None:
        """Apply a partial update dict to this calendar, ignoring unknown or immutable fields."""
        for field_name, value in updates.items():
            if field_name in self.MUTABLE_FIELDS:
                setattr(self, field_name, value)
