from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from app.module.calendar.CalendarConst import MAX_ICS_EVENTS, SYNC_LOCK_TTL_SECONDS
from app.module.calendar.model.CalEventSyncMeta import CalEventSyncMeta
from app.module.calendar.model.CalSyncResult import CalSyncResult
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.serializer.CalendarDeserializerIcal import CalendarDeserializerIcal
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from app.module.calendar.sync.IcsFetcher import IcsFetcher
from app.utils.calendar.DateTimeUtils import anchor_to_utc, to_utc
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.source.CalendarSources import CalendarSources


class SyncEngine:
    """Synchronizes an external ICS calendar by mirroring its events into the local database.

    Compares fetched events with existing DB rows by UID, then inserts new events,
    updates modified ones (by SEQUENCE or LAST-MODIFIED), and soft-deletes removed ones.

    Designed to be callable independently from the HTTP context — ready for Celery dispatch.
    """

    def __init__(self, sources: CalendarSources, cache: ClientRedis) -> None:
        self._sources = sources
        self._cache = cache
        self._deserializer = CalendarDeserializerIcal(
            CalendarEventsDeserializerIcal(CalendarEventDeserializerIcal())
        )

    def sync(self, calendar: CalCalendar) -> CalSyncResult:
        """Run a full sync for an ICS calendar.

        Acquires a Redis lock to prevent concurrent syncs on the same calendar.
        """
        if calendar.source_type != CalendarSourceType.ICS:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

        url: str | None = (calendar.sync_config or {}).get("url")
        if not url:
            raise RequestException(error=err.ERROR_CALENDAR_ICS_FETCH_FAILED)

        lock_key: str = f"sync_lock:{calendar.key}"
        lock_token: str = generate_uuid()
        if not self._cache.set(lock_key, lock_token, ttl=SYNC_LOCK_TTL_SECONDS, nx=True):
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

        self._update_sync_status(calendar, CalendarSyncStatus.RUNNING)
        try:
            username: str | None = (calendar.sync_config or {}).get("username")
            password: str | None = (calendar.sync_config or {}).get("password")
            ics_text: str = IcsFetcher.fetch(url, username=username, password=password)
            result: CalSyncResult = self.apply_ics(calendar, ics_text, delete_missing=True)
            self._update_sync_status(calendar, CalendarSyncStatus.COMPLETED)
            logger_calendar.info(
                "Sync completed for calendar %s: %d inserted, %d updated, %d deleted",
                calendar.key, result.inserted, result.updated, result.deleted,
            )
            return result
        except RequestException as exc:
            self._update_sync_status(calendar, CalendarSyncStatus.FAILED, error=exc.error.m if exc.error else "Sync failed")
            raise
        except Exception:
            logger_calendar.exception("Unexpected sync error for calendar %s", calendar.key)
            self._update_sync_status(calendar, CalendarSyncStatus.FAILED, error="Unexpected sync error")
            raise
        finally:
            # Only release the lock if we still own it (compare-and-swap)
            stored: str | None = cast("str | None", self._cache.get(lock_key, str))
            if stored == lock_token:
                self._cache.delete(lock_key)

    def apply_ics(
        self, calendar: CalCalendar, ics_text: str, *,
        delete_missing: bool, default_timezone: str | None = None,
        rewrite_owner_email: str | None = None,
        remove_attendees: bool = False,
    ) -> CalSyncResult:
        """Parse an ICS payload and apply it to the calendar via the upsert/diff pipeline.

        Public entry point shared by the URL-based sync (mirror an external feed) and the
        file-based import (merge a user-provided .ics into a local calendar).

        :param calendar: The target calendar (writes go through its CalendarSource).
        :param ics_text: Raw VCALENDAR payload to apply.
        :param delete_missing: When True, soft-delete local events absent from ``ics_text``
            (mirror semantics — used by external ICS sync). When False, only insert and
            update (additive semantics — used by user import, which must not erase the rest
            of the calendar).
        :param default_timezone: IANA timezone applied to datetimes that carry no explicit
            timezone (floating time). When None, naive datetimes are assumed UTC.
        :param rewrite_owner_email: When set, every parsed event has its ORGANIZER replaced
            with this email and its SEQUENCE reset to 0 — used by the import flow to make the
            importing user the sole owner of imported events. Attendees are left untouched.
        :param remove_attendees: When True, every parsed event has its ATTENDEE list cleared —
            used by the import flow when imported events must not carry over their original
            guest list. Defaults to False (attendees preserved).
        :return: Counters of inserted, updated and deleted rows.
        :raises RequestException: ERROR_CALENDAR_ICS_PARSE_FAILED if the payload exceeds
            ``MAX_ICS_EVENTS`` or cannot be deserialized.
        """
        remote_events: list[CalEvent] = self._deserializer.deserialize(ics_text).events
        if len(remote_events) > MAX_ICS_EVENTS:
            logger_calendar.error("ICS payload for calendar %s has too many events (%d)", calendar.key, len(remote_events))
            raise RequestException(error=err.ERROR_CALENDAR_ICS_PARSE_FAILED)
        if rewrite_owner_email:
            # Ownership rewrite on the deserialized models (never on the raw iCal text):
            # the importing user becomes the organizer and the revision history restarts
            # (RFC 5546 §2.1.4 — SEQUENCE belongs to the organizer). Attendees are kept.
            for event in remote_events:
                event.organizer = CalOrganizer(email=rewrite_owner_email)
                event.sequence = 0
        if remove_attendees:
            for event in remote_events:
                event.attendees = []
        return self._apply_diff(calendar, remote_events, delete_missing=delete_missing, default_timezone=default_timezone)

    def _apply_diff(  # pylint: disable=too-many-locals
        self, calendar: CalCalendar, remote_events: list[CalEvent], *,
        delete_missing: bool, default_timezone: str | None = None,
    ) -> CalSyncResult:
        """Compare remote events with local DB and apply inserts/updates, plus optional deletes.

        The sync engine writes directly to the source, bypassing the module ACL checks.
        ``delete_missing`` controls whether local rows absent from the payload are removed.
        ``default_timezone`` anchors floating datetimes (no explicit TZ) when set.
        """
        source = self._sources.get(calendar)
        local_metadata: list[CalEventSyncMeta] = source.get_sync_metadata()
        local_by_key: dict[tuple[str, datetime | None], CalEventSyncMeta] = {
            (m.uid, m.recurrence_id): m for m in local_metadata
        }

        remote_masters, remote_overrides, remote_keys = self._prepare_remote(
            remote_events, calendar.require_key, default_timezone=default_timezone,
        )

        # An override (RECURRENCE-ID) is only meaningful if its parent master is reachable:
        # either present in the same payload, or already persisted in the calendar. Google
        # Calendar (and other producers) sometimes export detached occurrences without their
        # master when the master falls outside the export window — skip those silently.
        known_master_uids: set[str] = {m.require_uid for m in remote_masters}
        known_master_uids.update(meta.uid for meta in local_metadata if meta.recurrence_id is None)

        inserted: int = 0
        updated: int = 0
        deleted: int = 0
        skipped: int = 0

        for remote_evt in remote_masters + remote_overrides:
            if remote_evt.recurrence_id is not None and remote_evt.uid not in known_master_uids:
                logger_calendar.warning(
                    "Orphan override skipped for calendar %s: uid=%s recurrence_id=%s (no master)",
                    calendar.key, remote_evt.uid, remote_evt.recurrence_id,
                )
                skipped += 1
                continue
            key = (remote_evt.require_uid, remote_evt.recurrence_id)
            if key not in local_by_key:
                if not remote_evt.key:
                    remote_evt.key = generate_uuid()
                source.insert_event(remote_evt)
                inserted += 1
            else:
                local_meta: CalEventSyncMeta = local_by_key[key]
                if self._is_modified_meta(local_meta, remote_evt):
                    remote_evt.key = local_meta.key
                    remote_evt.db_id = local_meta.db_id
                    source.update_event(remote_evt)
                    updated += 1

        # Mirror semantics (sync): a local event no longer present in the feed is removed.
        # Additive semantics (import): delete_missing is False, the rest of the calendar is
        # left intact so an import never erases events that were not in the uploaded file.
        if delete_missing:
            for key, local_meta in local_by_key.items():
                if key not in remote_keys:
                    source.delete_by_key(local_meta.key)
                    deleted += 1

        return CalSyncResult(
            inserted=inserted, updated=updated, deleted=deleted,
            total=len(remote_keys), skipped=skipped,
        )

    @staticmethod
    def _prepare_remote(
        remote_events: list[CalEvent], calendar_key: str, *,
        default_timezone: str | None = None,
    ) -> tuple[list[CalEvent], list[CalEvent], set[tuple[str, datetime | None]]]:
        """Sanitize, normalize UTC dates, and split remote events into masters and overrides.

        Datetimes that arrive without an explicit timezone (RFC 5545 floating time) are
        anchored to ``default_timezone`` when provided, otherwise treated as UTC.
        """
        masters: list[CalEvent] = []
        overrides: list[CalEvent] = []
        keys: set[tuple[str, datetime | None]] = set()
        for evt in remote_events:
            if not evt.uid:
                continue
            evt.sanitize()
            evt.calendar_key = calendar_key
            if evt.recurrence_id is not None:
                evt.recurrence_id = anchor_to_utc(evt.recurrence_id, default_timezone)
            if evt.date_start is not None:
                evt.date_start = anchor_to_utc(evt.date_start, default_timezone)
            if evt.date_end is not None:
                evt.date_end = anchor_to_utc(evt.date_end, default_timezone)
            keys.add((evt.uid, evt.recurrence_id))
            if evt.recurrence_id is not None:
                overrides.append(evt)
            else:
                masters.append(evt)
        return masters, overrides, keys

    def _update_sync_status(self, calendar: CalCalendar, status: CalendarSyncStatus, error: str | None = None) -> None:
        """Update sync_config with current status and timestamp."""
        if calendar.sync_config is None:
            calendar.sync_config = {}
        calendar.sync_config["sync_status"] = status.value
        calendar.sync_config["last_sync"] = datetime.now(timezone.utc).isoformat()
        if error:
            calendar.sync_config["sync_error"] = error
        elif "sync_error" in calendar.sync_config:
            del calendar.sync_config["sync_error"]
        self._sources.update_sync_config(calendar)

    @staticmethod
    def _is_modified_meta(local_meta: CalEventSyncMeta, remote: CalEvent) -> bool:
        """Determine if the remote event has been modified compared to the local metadata.

        Uses SEQUENCE (RFC 5545 §3.8.7.4) as primary indicator. Falls back to
        updated_at comparison if SEQUENCE is equal.
        """
        if remote.sequence > local_meta.sequence:
            return True
        if remote.sequence < local_meta.sequence:
            return False
        if remote.updated_at and local_meta.updated_at and to_utc(remote.updated_at) > to_utc(local_meta.updated_at):
            return True
        return False
