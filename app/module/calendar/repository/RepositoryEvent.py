from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalendarEventDeserializerJson import CalendarEventDeserializerJson
from app.module.calendar.serializer.CalendarEventSerializerJson import CalendarEventSerializerJson
from app.utils import errors as err
from app.utils.db.Condition import (AndCondition, EqualCondition, GreaterOrEqualCondition,
                                     IsNotNullCondition, IsNullCondition, LessOrEqualCondition, LikeCondition,
                                     OrCondition)
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_calendar
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalEvent import CalEvent


_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_EVT_COL)
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_EVT_COL if col.name != tbl.COL_ID.name)

_serializer = CalendarEventSerializerJson()
_deserializer = CalendarEventDeserializerJson()


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Return dt with UTC tzinfo. Naive datetimes are assumed to be UTC. None passes through."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class RepositoryEvent:
    """Handles all DB reads and writes for sogo_events."""

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    @staticmethod
    def _row_to_event(row: tuple) -> CalEvent:
        """Map a DB row (ordered per ALL_EVT_COL) to a CalEvent."""
        d = dict(zip(_ALL_COLS, row))
        blob = d[tbl.COL_EVT_CAL_EVENT.name]
        event = _deserializer.from_dict(blob)

        event.id = str(d[tbl.COL_ID.name])
        event.key = d[tbl.COL_EVT_KEY.name]
        event.calendar_key = d[tbl.COL_EVT_CALENDAR_KEY.name]
        event.uid = d[tbl.COL_EVT_UID.name]
        event.component_type = ComponentType(d[tbl.COL_EVT_COMPONENT_TYPE.name])
        event.date_start = _ensure_utc(d[tbl.COL_EVT_DATE_START.name])
        event.date_end = _ensure_utc(d[tbl.COL_EVT_DATE_END.name])
        event.sequence = d[tbl.COL_EVT_SEQUENCE.name]
        event.recurrence_id = _ensure_utc(d[tbl.COL_EVT_RECURRENCE_ID.name])
        event.created_at = _ensure_utc(d[tbl.COL_EVT_CREATED_AT.name])
        event.updated_at = _ensure_utc(d[tbl.COL_EVT_UPDATED_AT.name])
        return event

    @staticmethod
    def _build_search_vector(event: CalEvent) -> str:
        """Build a plain-text search vector from title, description and location."""
        parts = [event.title or ""]
        if event.description:
            parts.append(event.description)
        if event.location:
            parts.append(event.location)
        return " ".join(parts)

    @staticmethod
    def _date_end_recurrence(event: CalEvent) -> datetime | None:
        """Return the last possible occurrence datetime for a recurring event, or None."""
        if event.recurrence_rule is None:
            return None
        return event.recurrence_rule.until

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
        When search is provided, a LIKE/ILIKE filter is applied against the search_vector column.
        """
        non_recurring = AndCondition(
            IsNullCondition(tbl.COL_EVT_RRULE.name),
            AndCondition(
                LessOrEqualCondition(tbl.COL_EVT_DATE_START.name, end),
                GreaterOrEqualCondition(tbl.COL_EVT_DATE_END.name, start),
            ),
        )
        recurring = AndCondition(
            IsNotNullCondition(tbl.COL_EVT_RRULE.name),
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
        if search:
            condition = AndCondition(condition, LikeCondition(tbl.COL_EVT_SEARCH_VECTOR.name, f"%{search}%"))
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            sort_by=tbl.COL_EVT_DATE_START.name,
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
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        if not rows:
            return None
        return self._row_to_event(rows[0])

    def insert(self, event: CalEvent) -> CalEvent:
        """Persist a new event and return it with id and key populated."""
        now = datetime.now(timezone.utc)
        event.key = generate_uuid()
        event.created_at = now
        event.updated_at = now

        rrule_dict = event.recurrence_rule.to_dict() if event.recurrence_rule else None
        blob = _serializer.to_dict(event)

        values = [[
            event.key,
            event.calendar_key,
            event.uid,
            event.component_type.value,
            event.date_start,
            event.date_end,
            event.show_as.value,
            rrule_dict,
            self._date_end_recurrence(event),
            event.recurrence_id,
            None,
            False,
            event.sequence,
            self._build_search_vector(event),
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

        fetched = self.find_by_key(event.calendar_key, event.key)
        if fetched is None:
            logger_calendar.error("Event key=%s was inserted but could not be fetched back", event.key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED)

        return fetched

    def update(self, event: CalEvent) -> None:
        """Update an existing event. event.id must be set."""
        if event.id is None:
            raise BugException("RepositoryEvent.update called with event.id=None")

        now = datetime.now(timezone.utc)
        event.updated_at = now
        rrule_dict = event.recurrence_rule.to_dict() if event.recurrence_rule else None
        blob = _serializer.to_dict(event)

        update_cols = (
            tbl.COL_EVT_UID.name,
            tbl.COL_EVT_COMPONENT_TYPE.name,
            tbl.COL_EVT_DATE_START.name,
            tbl.COL_EVT_DATE_END.name,
            tbl.COL_EVT_SHOW_AS.name,
            tbl.COL_EVT_RRULE.name,
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
            rrule_dict,
            self._date_end_recurrence(event),
            event.recurrence_id,
            event.sequence,
            self._build_search_vector(event),
            blob,
            event.updated_at,
        ]

        updated = self._db.update_in_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=update_cols,
            values_list=values,
            condition=EqualCondition(tbl.COL_ID.name, int(event.id)),
        )

        if updated == 0:
            logger_calendar.error("Event id=%s not found on update", event.id)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)

    def delete(self, calendar_key: str, uid: str) -> None:
        """Soft-delete an event by uid within a calendar."""
        now = datetime.now(timezone.utc)
        self._db.update_in_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
            values_list=[True, now],
            condition=AndCondition(
                EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
                EqualCondition(tbl.COL_EVT_UID.name, uid),
            ),
        )

    def delete_all(self, calendar_key: str) -> None:
        """Soft-delete all events belonging to a calendar."""
        now = datetime.now(timezone.utc)
        self._db.update_in_table(
            table_name=tbl.TABLE_EVENT.name,
            column_tuple=(tbl.COL_EVT_IS_DELETED.name, tbl.COL_EVT_UPDATED_AT.name),
            values_list=[True, now],
            condition=EqualCondition(tbl.COL_EVT_CALENDAR_KEY.name, calendar_key),
        )
