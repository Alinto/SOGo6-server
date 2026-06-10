from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.utils.calendar.DateTimeUtils import to_utc
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventSyncMeta import CalEventSyncMeta
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalendarEventDeserializerDict import CalendarEventDeserializerDict
from app.module.calendar.serializer.CalendarEventSerializerDict import CalendarEventSerializerDict
from app.utils import errors as err
from app.utils.db.Condition import (AndCondition, EqualCondition, FullTextCondition, GreaterOrEqualCondition,
                                     IsNotNullCondition, IsNullCondition, LessOrEqualCondition,
                                     NotEqualCondition, OrCondition)
from app.utils.db.FullTextValue import FullTextValue
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_calendar
from app.utils.maths.sogo_hash import generate_uuid
from app.utils.strings import strip_accents

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_EVT_COL)
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_EVT_COL if col.name != tbl.COL_ID.name)

_serializer = CalendarEventSerializerDict()
_deserializer = CalendarEventDeserializerDict()

class RepositoryEvent:
    """Handles all DB reads and writes for sogo_events."""

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    @staticmethod
    def _build_search_vector(event: CalEvent) -> str:
        """Build a plain-text, accent-insensitive search index from title, description and location.

        The same normalization (strip_accents) is applied to the stored search vector and to the
        query, so the match works regardless of the PostgreSQL text-search config or the MariaDB
        collation.
        """
        parts = [event.title or ""]
        if event.description:
            parts.append(event.description)
        if event.location:
            parts.append(event.location)
        return strip_accents(" ".join(parts))

    @staticmethod
    def _row_to_event(row: tuple) -> CalEvent:
        """Map a DB row (ordered per ALL_EVT_COL) to a CalEvent."""
        d = dict(zip(_ALL_COLS, row))
        blob = d[tbl.COL_EVT_CAL_EVENT.name]
        event = _deserializer.deserialize(blob)

        event.db_id = d[tbl.COL_ID.name]
        event.key = d[tbl.COL_EVT_KEY.name]
        event.calendar_key = d[tbl.COL_EVT_CALENDAR_KEY.name]
        event.uid = d[tbl.COL_EVT_UID.name]
        event.component_type = ComponentType(d[tbl.COL_EVT_COMPONENT_TYPE.name])
        event.date_start = to_utc(d[tbl.COL_EVT_DATE_START.name])
        event.date_end = to_utc(d[tbl.COL_EVT_DATE_END.name]) if d[tbl.COL_EVT_DATE_END.name] is not None else None
        event.sequence = d[tbl.COL_EVT_SEQUENCE.name]
        event.recurrence_id = to_utc(d[tbl.COL_EVT_RECURRENCE_ID.name]) if d[tbl.COL_EVT_RECURRENCE_ID.name] is not None else None
        event.created_at = to_utc(d[tbl.COL_EVT_CREATED_AT.name]) if d[tbl.COL_EVT_CREATED_AT.name] is not None else None
        event.updated_at = to_utc(d[tbl.COL_EVT_UPDATED_AT.name]) if d[tbl.COL_EVT_UPDATED_AT.name] is not None else None
        return event

    def find_by_calendar(
        self,
        calendar_key: str,
        start: datetime,
        end: datetime,
        search: str | None = None,
        component_type: ComponentType = ComponentType.EVENT,
    ) -> list[CalEvent]:
        """Return all non-deleted components of the given type for a calendar overlapping [start, end].

        Non-recurring: date_start <= end AND date_end >= start.
        Recurring: date_start <= end AND (date_end_recurrence IS NULL OR date_end_recurrence >= start).
        When search is provided, a full-text filter is applied against the search_vector column
        (word/token match via the database full-text index, not a substring match), and results
        are ordered by relevance first, then by date_start as a tiebreaker.
        """
        non_recurring = AndCondition(
            EqualCondition(tbl.COL_EVT_IS_RECURRING.name, False),
            AndCondition(
                LessOrEqualCondition(tbl.COL_EVT_DATE_START.name, end),
                OrCondition(
                    IsNullCondition(tbl.COL_EVT_DATE_END.name),
                    GreaterOrEqualCondition(tbl.COL_EVT_DATE_END.name, start),
                ),
            ),
        )
        recurring = AndCondition(
            EqualCondition(tbl.COL_EVT_IS_RECURRING.name, True),
            AndCondition(
                LessOrEqualCondition(tbl.COL_EVT_DATE_START.name, end),
                OrCondition(
                    IsNullCondition(tbl.COL_EVT_DATE_END_RECUR.name),
                    GreaterOrEqualCondition(tbl.COL_EVT_DATE_END_RECUR.name, start),
                ),
            ),
        )
        condition = AndCondition(
            AndCondition(
                AndCondition(
                    EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                    EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
                ),
                EqualCondition(tbl.COL_EVT_COMPONENT_TYPE.name, component_type.value),
            ),
            OrCondition(non_recurring, recurring),
        )
        search_condition = (
            FullTextCondition(tbl.COL_EVT_SEARCH_VECTOR.name, strip_accents(search))
            if search else None
        )
        if search_condition is not None:
            condition = AndCondition(condition, search_condition)
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            sort_by=tbl.COL_EVT_DATE_START.name,
            rank_by=search_condition,
        )
        return [self._row_to_event(row) for row in rows]

    def find_by_key(self, calendar_key: str, key: str) -> CalEvent | None:
        """Return a single event by key within the given calendar, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_EVT_KEY.name, key),
                EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
            ),
            EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_event(rows[0])

    def insert(self, event: CalEvent, date_end_recurrence: datetime | None = None) -> CalEvent:
        """Persist a new event and return it with id and key populated."""
        now = datetime.now(timezone.utc)
        event.key = generate_uuid()
        event.created_at = now
        event.updated_at = now

        blob = _serializer.serialize(event)
        for field_name in CalEvent.UNPERSISTED_FIELDS:
            blob.pop(field_name, None)

        values = [[
            event.key,
            event.calendar_key,
            event.uid,
            event.component_type.value,
            event.date_start,
            event.date_end,
            event.show_as.value,
            event.recurrence_rule is not None,
            date_end_recurrence,
            event.recurrence_id,
            False,
            event.sequence,
            FullTextValue(RepositoryEvent._build_search_vector(event)),
            blob,
            event.created_at,
            event.updated_at,
        ]]

        try:
            inserted = self._db.insert_in_table(
                table_name=tbl.TABLE_EVENT.name,
                column_tuple=_INSERT_COLS,
                values_tuple=values,
            )
        except BugException as exc:
            logger_calendar.error("Unique violation inserting event uid=%s calendar=%s: %s", event.uid, event.calendar_key, exc)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_DUPLICATE) from exc

        if inserted != 1:
            logger_calendar.error("Event insert affected %s rows instead of 1 (uid=%s)", inserted, event.uid)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED)

        fetched = self.find_by_key(event.require_calendar_key, event.require_key)
        if fetched is None:
            logger_calendar.error("Event key=%s was inserted but could not be fetched back", event.key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED)

        return fetched

    def update(self, event: CalEvent, date_end_recurrence: datetime | None = None) -> None:
        """Update an existing event. event.db_id must be set."""
        if event.db_id is None:
            raise BugException("RepositoryEvent.update called with event.db_id=None")

        now = datetime.now(timezone.utc)
        event.updated_at = now
        blob = _serializer.serialize(event)
        for field_name in CalEvent.UNPERSISTED_FIELDS:
            blob.pop(field_name, None)

        update_cols = (
            tbl.COL_EVT_UID.name,
            tbl.COL_EVT_COMPONENT_TYPE.name,
            tbl.COL_EVT_DATE_START.name,
            tbl.COL_EVT_DATE_END.name,
            tbl.COL_EVT_SHOW_AS.name,
            tbl.COL_EVT_IS_RECURRING.name,
            tbl.COL_EVT_DATE_END_RECUR.name,
            tbl.COL_EVT_RECURRENCE_ID.name,
            tbl.COL_EVT_SEQUENCE.name,
            tbl.COL_EVT_SEARCH_VECTOR.name,
            tbl.COL_EVT_CAL_EVENT.name,
            tbl.COL_EVT_UPDATED_AT.name,
        )
        values = [
            event.uid,
            event.component_type.value,
            event.date_start,
            event.date_end,
            event.show_as.value,
            event.recurrence_rule is not None,
            date_end_recurrence,
            event.recurrence_id,
            event.sequence,
            FullTextValue(RepositoryEvent._build_search_vector(event)),
            blob,
            event.updated_at,
        ]

        updated = self._db.update_in_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=update_cols,
            values_list=values,
            condition=EqualCondition(tbl.COL_ID.name, event.db_id),
        )

        if updated == 0:
            logger_calendar.error("Event db_id=%s not found on update", event.db_id)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)

    def find_master_by_uid(self, calendar_key: str, uid: str) -> CalEvent | None:
        """Return the master event (recurrence_id IS NULL) for the given UID, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                EqualCondition(tbl.COL_EVT_UID.name, uid),
            ),
            AndCondition(
                IsNullCondition(tbl.COL_EVT_RECURRENCE_ID.name),
                EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
            ),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_event(rows[0])

    def find_by_recurrence_id(self, calendar_key: str, uid: str, recurrence_id: datetime) -> CalEvent | None:
        """Return the detached occurrence matching uid + recurrence_id, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                EqualCondition(tbl.COL_EVT_UID.name, uid),
            ),
            AndCondition(
                EqualCondition(tbl.COL_EVT_RECURRENCE_ID.name, recurrence_id),
                EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
            ),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_event(rows[0])

    def delete_by_key(self, calendar_key: str, key: str, hard_delete: bool = False) -> None:
        """Soft-delete (or hard-delete) a single event row by its opaque key.

        Does not affect other rows sharing the same uid.
        """
        condition = AndCondition(
            EqualCondition(tbl.COL_EVT_KEY.name, key),
            EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
        )
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_EVENT.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_EVENT.name,
                column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
                values_list=[True, now],
                condition=condition,
            )

    def find_detached_occurrences(self, calendar_key: str, uid: str) -> list[CalEvent]:
        """Return all non-deleted detached occurrences (recurrence_id IS NOT NULL) for a master UID."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                EqualCondition(tbl.COL_EVT_UID.name, uid),
            ),
            AndCondition(
                IsNotNullCondition(tbl.COL_EVT_RECURRENCE_ID.name),
                EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
            ),
        )
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            sort_by=tbl.COL_EVT_RECURRENCE_ID.name,
        )
        return [self._row_to_event(row) for row in rows]

    def delete_occurrence(self, calendar_key: str, uid: str, recurrence_id: datetime) -> None:
        """Soft-delete a specific detached occurrence identified by UID and recurrence_id."""
        now = datetime.now(timezone.utc)
        self._db.update_in_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
            values_list=[True, now],
            condition=AndCondition(
                AndCondition(
                    EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                    EqualCondition(tbl.COL_EVT_UID.name, uid),
                ),
                EqualCondition(tbl.COL_EVT_RECURRENCE_ID.name, recurrence_id),
            ),
        )

    def delete(self, calendar_key: str, uid: str, hard_delete: bool = False) -> None:
        """Soft-delete (or hard-delete) an event by uid within a calendar.

        When hard_delete=True the row is permanently removed from the table.
        """
        condition = AndCondition(
            EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
            EqualCondition(tbl.COL_EVT_UID.name, uid),
        )
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_EVENT.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_EVENT.name,
                column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
                values_list=[True, now],
                condition=condition,
            )

    def find_keys(self, calendar_key: str) -> list[str]:
        """Return all non-deleted event keys for a calendar."""
        condition = AndCondition(
            EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
            EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
        )
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=(tbl.COL_EVT_KEY.name,),
            condition=condition,
        )
        return [row[0] for row in rows]

    def find_sync_metadata(self, calendar_key: str) -> list[CalEventSyncMeta]:
        """Return lightweight metadata for all non-deleted events in a calendar.

        Avoids loading full event blobs for large calendars.
        """
        cols = (tbl.COL_ID.name, tbl.COL_EVT_KEY.name, tbl.COL_EVT_UID.name,
                tbl.COL_EVT_RECURRENCE_ID.name, tbl.COL_EVT_SEQUENCE.name, tbl.COL_EVT_UPDATED_AT.name)
        condition = AndCondition(
            EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
            EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
        )
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=cols,
            condition=condition,
        ))
        return [CalEventSyncMeta(
            db_id=r[0], key=r[1], uid=r[2],
            recurrence_id=to_utc(r[3]) if r[3] is not None else None,
            sequence=r[4],
            updated_at=to_utc(r[5]) if r[5] is not None else None,
        ) for r in rows]

    def delete_all(self, calendar_key: str, hard_delete: bool = False) -> None:
        """Soft-delete (or hard-delete) all events belonging to a calendar."""
        condition = EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key)
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_EVENT.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_EVENT.name,
                column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
                values_list=[True, now],
                condition=condition,
            )

    def find_all_by_uid(
        self, uid: str, exclude_organizer_calendar_key: str | None = None, recurrence_id: datetime | None = None,
    ) -> list[CalEvent]:
        """Return all non-deleted event rows with the given UID across all calendars.

        When recurrence_id is None, returns master rows (recurrence_id IS NULL).
        When recurrence_id is provided, returns detached occurrences matching that date.
        When exclude_organizer_calendar_key is provided, the organizer's own calendar is excluded.
        """
        recurrence_cond = (
            EqualCondition(tbl.COL_EVT_RECURRENCE_ID.name, recurrence_id)
            if recurrence_id is not None
            else IsNullCondition(tbl.COL_EVT_RECURRENCE_ID.name)
        )
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_EVT_UID.name, uid),
                recurrence_cond,
            ),
            EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
        )
        if exclude_organizer_calendar_key is not None:
            condition = AndCondition(
                condition,
                NotEqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, exclude_organizer_calendar_key),
            )
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
        )
        return [self._row_to_event(row) for row in rows]

    def delete_all_by_uid(self, uid: str, exclude_organizer_calendar_key: str | None = None) -> None:
        """Soft-delete all non-deleted rows with the given UID across all calendars.

        When exclude_organizer_calendar_key is provided, the organizer's calendar rows are preserved.
        Used when an organizer cancels an event to propagate the deletion to all attendee copies.
        """
        now: datetime = datetime.now(timezone.utc)
        condition = AndCondition(
            EqualCondition(tbl.COL_EVT_UID.name, uid),
            EqualCondition(tbl.COL_EVT_IS_DELETED.name, False),
        )
        if exclude_organizer_calendar_key is not None:
            condition = AndCondition(
                condition,
                NotEqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, exclude_organizer_calendar_key),
            )
        self._db.update_in_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
            values_list=[True, now],
            condition=condition,
        )

    def purge_deleted(self, calendar_key: str) -> int:
        """Physically remove all soft-deleted event rows for a calendar.

        Returns the number of rows deleted. Call this after delete_calendar() to reclaim
        DB space once the soft-deleted rows are no longer needed for CalDAV sync reports.
        """
        return self._db.delete_row_in_table(
            table_name=tbl.TABLE_EVENT.name,
            condition=AndCondition(
                EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                EqualCondition(tbl.COL_EVT_IS_DELETED.name, True),
            ),
        )
