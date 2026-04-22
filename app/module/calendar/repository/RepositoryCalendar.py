from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.calendar.model.CalCalendar import CalCalendar
from app.utils import errors as err
from app.utils.db.Condition import AndCondition, EqualCondition, NotEqualCondition
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


# All column names in ALL_CAL_COL order — used for SELECT and row mapping
_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_CAL_COL)

# Columns for INSERT — id is serial, omitted
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_CAL_COL if col.name != tbl.COL_ID.name)


class RepositoryCalendar:
    """Handles all DB reads and writes for sogo_calendar_calendars."""

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    @staticmethod
    def _row_to_calendar(row: tuple) -> CalCalendar:
        """Map a DB row (ordered per ALL_CAL_COL) to a CalCalendar."""
        d = dict(zip(_ALL_COLS, row))
        return CalCalendar(
            id=d["id"],
            key=d["key"],
            user_uid=d["user_uid"],
            is_default=bool(d["is_default"]),
            source_type=d["source_type"],
            name=d["name"],
            color=d["color"],
            description=d["description"],
            timezone=d["timezone"],
            share_token=d["share_token"],
            ctag=d["ctag"],
            sync_config=d["sync_config"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def insert(self, cal: CalCalendar) -> CalCalendar:
        """Persist a new calendar and return it with id populated."""
        now = datetime.now(timezone.utc)
        cal.created_at = now
        cal.updated_at = now
        values = [[
            cal.key,
            cal.user_uid,
            cal.is_default,
            cal.source_type,
            cal.name,
            cal.color,
            cal.description,
            cal.timezone,
            cal.share_token,
            cal.ctag,
            cal.sync_config,
            cal.created_at,
            cal.updated_at,
        ]]

        try:
            inserted = self._db.insert_in_table(
                table_name=tbl.TABLE_CALENDAR.name,
                column_tuple=_INSERT_COLS,
                values_tuple=values,
            )
        except BugException as exc:
            logger_calendar.error("Unique violation inserting calendar key=%s user=%s: %s", cal.key, cal.user_uid, exc)
            raise RequestException(error=err.ERROR_CALENDAR_DUPLICATE) from exc

        if inserted != 1:
            logger_calendar.error("Calendar insert affected %s rows instead of 1 (key=%s)", inserted, cal.key)
            raise BugException("Calendar insert did not affect exactly 1 row")

        fetched = self.find_by_key(cal.user_uid, cal.key)
        if fetched is None:
            raise BugException(f"Calendar key={cal.key} was inserted but could not be fetched back")
        return fetched

    def find_by_key(self, user_uid: str, key: str) -> CalCalendar | None:
        """Return the calendar matching (user_uid, key), or None if not found."""
        condition = AndCondition(
            EqualCondition(tbl.COL_CAL_USER_UID.name, user_uid),
            EqualCondition(tbl.COL_CAL_KEY.name, key),
        )
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_CALENDAR.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))

        if not rows:
            return None
        return self._row_to_calendar(rows[0])

    def find_all(self, user_uid: str) -> list[CalCalendar]:
        """Return all calendars for the given user, ordered by id."""
        condition = EqualCondition(tbl.COL_CAL_USER_UID.name, user_uid)
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CALENDAR.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            sort_by=tbl.COL_ID.name,
        )
        return [self._row_to_calendar(row) for row in rows]

    def update(self, cal: CalCalendar) -> None:
        """Update all mutable columns of an existing calendar. cal.id must be set."""
        if cal.id is None:
            raise BugException("RepositoryCalendar.update called with cal.id=None")

        cal.updated_at = datetime.now(timezone.utc)
        update_cols = (
            tbl.COL_CAL_NAME.name,
            tbl.COL_CAL_COLOR.name,
            tbl.COL_CAL_DESCRIPTION.name,
            tbl.COL_CAL_TIMEZONE.name,
            tbl.COL_CAL_IS_DEFAULT.name,
            tbl.COL_CAL_CTAG.name,
            tbl.COL_CAL_SYNC_CONFIG.name,
            tbl.COL_CAL_SHARE_TOKEN.name,
            tbl.COL_CAL_UPDATED_AT.name,
        )
        values = [
            cal.name,
            cal.color,
            cal.description,
            cal.timezone,
            cal.is_default,
            cal.ctag,
            cal.sync_config,
            cal.share_token,
            cal.updated_at,
        ]

        updated = self._db.update_in_table(
            table_name=tbl.TABLE_CALENDAR.name,
            column_tuple=update_cols,
            values_list=values,
            condition=EqualCondition(tbl.COL_ID.name, cal.id),
        )

        if updated == 0:
            logger_calendar.error("Calendar id=%s not found on update", cal.id)
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)

    def clear_default(self, user_uid: str, exclude_id: int) -> None:
        """Set is_default=False on every calendar of user_uid except exclude_id."""
        condition = AndCondition(
            EqualCondition(tbl.COL_CAL_USER_UID.name, user_uid),
            NotEqualCondition(tbl.COL_ID.name, exclude_id),
        )
        self._db.update_in_table(
            table_name=tbl.TABLE_CALENDAR.name,
            column_tuple=(tbl.COL_CAL_IS_DEFAULT.name,),
            values_list=[False],
            condition=condition,
        )

    def delete(self, cal_id: int) -> None:
        """Physically delete a calendar row. The caller must delete its events first."""
        deleted = self._db.delete_row_in_table(
            table_name=tbl.TABLE_CALENDAR.name,
            condition=EqualCondition(tbl.COL_ID.name, cal_id),
            expected_row=1,
        )

        if deleted == 0:
            logger_calendar.error("Calendar id=%s not found on delete", cal_id)
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
