from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.utils.calendar.DateTimeUtils import to_utc
from app.utils.db.Condition import AndCondition, EqualCondition, GreaterOrEqualCondition, JoinClause, LessOrEqualCondition

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalEvent import CalEvent

_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_REM_COL if col.name != tbl.COL_ID.name)


class RepositoryReminder:
    """Handles all DB reads and writes for sogo_calendar_reminders."""

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    def upsert(self, event: CalEvent) -> None:
        """Delete existing reminders for this event then insert fresh rows from event.reminders."""
        self.delete(event.key)
        if not event.reminders or event.date_start is None:
            return
        now: datetime = datetime.now(timezone.utc)
        for reminder in event.reminders:
            trigger_at: datetime = event.date_start - timedelta(minutes=reminder.minutes_before)
            self._db.insert_in_table(
                table_name=tbl.TABLE_REMINDER.name,
                column_tuple=_INSERT_COLS,
                values_tuple=[[
                    event.key,
                    reminder.method.value,
                    reminder.minutes_before,
                    trigger_at,
                    False,
                    now,
                    now,
                ]],
            )

    def delete(self, event_key: str) -> None:
        """Soft-delete all reminder rows for a given event key."""
        self._db.update_in_table(
            table_name=tbl.TABLE_REMINDER.name,
            column_tuple=(tbl.COL_REM_IS_DELETED.name, tbl.COL_REM_UPDATED_AT.name),
            values_list=[True, datetime.now(timezone.utc)],
            condition=EqualCondition(tbl.COL_REM_EVENT_KEY.name, event_key),
        )

    def purge_deleted(self, event_key: str | None = None) -> int:
        """Physically remove soft-deleted reminder rows."""
        condition = EqualCondition(tbl.COL_REM_IS_DELETED.name, True)
        if event_key is not None:
            condition = AndCondition(condition, EqualCondition(tbl.COL_REM_EVENT_KEY.name, event_key))
        return self._db.delete_row_in_table(
            table_name=tbl.TABLE_REMINDER.name,
            condition=condition,
        )

    def find_pending(
        self,
        start: datetime,
        end: datetime,
        user_uid: str | None = None,
        method: ReminderMethod | None = None,
    ) -> list[dict]:
        """Return non-deleted reminder rows with trigger_at in [start, end].

        Uses INNER JOIN on sogo_events and sogo_calendars to filter by user
        and exclude soft-deleted events in a single SQL query.
        """
        rem: str = tbl.TABLE_REMINDER.name
        evt: str = tbl.TABLE_EVENT.name
        cal: str = tbl.TABLE_CALENDAR.name

        q_trigger: str = f"{rem}.{tbl.COL_REM_TRIGGER_AT.name}"
        q_rem_deleted: str = f"{rem}.{tbl.COL_REM_IS_DELETED.name}"
        q_evt_deleted: str = f"{evt}.{tbl.COL_EVT_IS_DELETED.name}"

        find_cols: tuple[str, ...] = (
            f"{rem}.{tbl.COL_REM_EVENT_KEY.name}",
            f"{rem}.{tbl.COL_REM_METHOD.name}",
            f"{rem}.{tbl.COL_REM_MINUTES.name}",
            f"{rem}.{tbl.COL_REM_TRIGGER_AT.name}",
            f"{evt}.{tbl.COL_EVT_DATE_START.name}",
            f"{evt}.{tbl.COL_EVT_DATE_END.name}",
            f"{evt}.{tbl.COL_EVT_IS_RECURRING.name}",
        )

        condition = AndCondition(
            AndCondition(
                GreaterOrEqualCondition(q_trigger, start),
                LessOrEqualCondition(q_trigger, end),
            ),
            AndCondition(
                EqualCondition(q_rem_deleted, False),
                EqualCondition(q_evt_deleted, False),
            ),
        )
        if user_uid is not None:
            condition = AndCondition(condition, EqualCondition(f"{cal}.user_uid", user_uid))
        if method is not None:
            condition = AndCondition(condition, EqualCondition(f"{rem}.{tbl.COL_REM_METHOD.name}", method.value))

        joins: list[JoinClause] = [
            JoinClause(table=evt, left_col=f"{rem}.{tbl.COL_REM_EVENT_KEY.name}", right_col=f"{evt}.{tbl.COL_EVT_KEY.name}"),
            JoinClause(table=cal, left_col=f"{evt}.{tbl.COL_EVT_CALENDAR_KEY.name}", right_col=f"{cal}.key"),
        ]

        rows = self._db.select_from_several_table(
            table_name=rem,
            joins=joins,
            column_tuple=find_cols,
            condition=condition,
            sort_by=q_trigger,
        )
        return [self._join_row_to_dict(row) for row in rows]

    @staticmethod
    def _join_row_to_dict(row: tuple) -> dict:
        return {
            "event_key": row[0],
            "method": row[1],
            "minutes_before": row[2],
            "trigger_at": to_utc(row[3]) if row[3] is not None else None,
            "date_start": to_utc(row[4]) if row[4] is not None else None,
            "date_end": to_utc(row[5]) if row[5] is not None else None,
            "is_recurring": row[6],
        }
