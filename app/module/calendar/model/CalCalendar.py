from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus
from app.utils.datetime.DateTimeUtils import parse_iso, to_utc
from app.utils.exceptions import BugException

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.CalendarPermissions import CalendarPermissions
    from app.module.calendar.model.enums.EventVisibility import EventVisibility


@dataclass
class CalCalendar:  # pylint: disable=too-many-instance-attributes,invalid-name
    """
    Format-agnostic representation of a calendar (RFC 4791 §4.2 calendar collection).

    Maps to sogo_calendar_calendars. id is the internal integer PK; key is the opaque
    public identifier exposed in the API (prevents row enumeration).

    source_type drives CalendarSources dispatch:
      'local'  - personal calendar stored in DB, full CRUD
      'ics'    - read-only subscription to a remote .ics URL (RFC 5545 / WebDAV)
      'caldav' - read-write sync with a remote CalDAV server (RFC 4791)

    External sync metadata (URL, credentials, etag, last_sync) lives in sync_config JSON.
    prodid, calscale, method are VCALENDAR-level properties not stored in DB - populated
    only when building from an ICS source (import/export).
    """
    # Internal - owner's uid, FK to sogo_user_profiles.uid
    user_uid: str
    # RFC 4918 §15.2 - display name of the calendar collection (DAV:displayname)
    name: str

    # Internal - database auto-increment PK
    id: int | None = None
    # Internal - opaque token exposed in the API (see generate_uuid)
    key: str | None = None
    # RFC 7986 §5.9 COLOR - hex color #RRGGBB for UI display
    color: str | None = None
    # RFC 4791 §5.2.1 - free-text description (DAV:comment or CALDAV:calendar-description)
    description: str | None = None
    # RFC 5545 §3.2.19 TZID - default IANA timezone for new events (e.g. "Europe/Paris")
    timezone: str = "UTC"
    # Internal - marks the user's primary personal calendar; uniqueness enforced by service layer
    is_default: bool = False
    # Internal - discriminates calendar backend: local, ics, caldav
    source_type: CalendarSourceType = CalendarSourceType.UNDEFINED
    # CalDAV CS:getctag extension (draft-daboo-caldav-extensions) - opaque token incremented
    # by the service layer on every event mutation (insert / update / delete).
    # CalDAV clients compare it against their cached value to detect changes without
    # fetching the full event list - avoids unnecessary sync traffic.
    ctag: int = 0
    # Internal - opaque token for the public .ics subscription URL.
    # Stored as a relational column (not in JSON) because it is queried directly:
    # WHERE share_token = ?
    share_token: str | None = None
    # External sync metadata - NULL for source_type='local'.
    # Schema: {url, username, password (AES-encrypted), etag, last_sync,
    #          sync_interval_minutes}
    sync_config: dict | None = None

    # Internal - when False, this calendar's events are excluded from the owner's free/busy.
    include_in_freebusy: bool = True
    # UI preference - default duration in minutes for a new timed event with no explicit end.
    # None means "use the global default" (the event keeps whatever end the caller provided).
    default_event_duration_min: int | None = None
    # UI preference - default offset in minutes for an alarm added without an explicit one.
    # None means "use the global default" (DEFAULT_REMINDER_MINUTES).
    default_alarm_duration_min: int | None = None
    # UI preference - default visibility (RFC 5545 CLASS) for new events. None means "use the
    # global default" (public).
    default_type: EventVisibility | None = None

    # RFC 5545 §3.7.3 PRODID - identifies the product that created the VCALENDAR object
    prodid: str | None = None
    # RFC 5545 §3.7.1 CALSCALE - calendar scale, almost always "GREGORIAN"
    calscale: str | None = None
    # RFC 5546 §1.4 METHOD - iTIP method (REQUEST, REPLY, CANCEL...) for iMIP messages
    method: str | None = None
    # Catch-all for non-standard VCALENDAR-level X-* properties
    extra_properties: dict[str, str] = field(default_factory=dict)

    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Transient - populated at read time by CalendarAclEngine, not persisted.
    permissions: CalendarPermissions | None = None

    # Transient - the calendar collection's components (RFC 4791), populated when serializing
    # to or deserializing from a full VCALENDAR. Not persisted: events live in their own table.
    events: list[CalEvent] = field(default_factory=list)

    _MUTABLE_FIELDS: frozenset[str] = frozenset({"name", "color", "description", "timezone", "is_default", "sync_config",
                                                 "include_in_freebusy", "default_event_duration_min",
                                                 "default_alarm_duration_min", "default_type"})

    @property
    def require_id(self) -> int:
        """Internal PK, guaranteed once the calendar has been persisted/loaded."""
        if self.id is None:
            raise BugException("CalCalendar.id accessed before the calendar was persisted")
        return self.id

    @property
    def require_key(self) -> str:
        """Opaque public key, guaranteed once the calendar has been persisted/loaded."""
        if self.key is None:
            raise BugException("CalCalendar.key accessed before the calendar was persisted")
        return self.key

    def apply_update(self, updates: dict[str, Any]) -> None:
        """Apply a partial update dict to this calendar, ignoring unknown or immutable fields."""
        for field_name, value in updates.items():
            if field_name in self._MUTABLE_FIELDS:
                setattr(self, field_name, value)

    def is_sync_due(self, now: datetime) -> bool:
        """Return True when this external calendar is due for an auto-sync (interval elapsed, not running)."""
        config: dict = self.sync_config or {}
        if config.get("sync_status") == CalendarSyncStatus.RUNNING.value:
            return False
        last_sync_raw: str | None = config.get("last_sync")
        if not last_sync_raw:
            return True  # never synced yet
        last_sync: datetime | None = parse_iso(last_sync_raw)
        if last_sync is None:
            return True
        interval_minutes: int = int(config.get("sync_interval_minutes") or 60)
        return (now - to_utc(last_sync)) >= timedelta(minutes=interval_minutes)
