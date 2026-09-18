from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.utils import errors as err
from app.utils.db.Condition import AndCondition, EqualCondition, NotEqualCondition
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_contact

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


# All column names in ALL_AB_COL order - used for SELECT and row mapping
_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_AB_COL)

# Columns for INSERT - id is serial, omitted
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_AB_COL if col.name != tbl.COL_ID.name)


class RepositoryAddressBook:
    """Handles all DB reads and writes for sogo6_contacts_addressbooks."""

    def __init__(self, db: ClientSQL) -> None:
        """Bind the repository to a SQL client."""
        self._db = db

    @staticmethod
    def _row_to_addressbook(row: tuple) -> CardAddressBook:
        """Map a DB row (ordered per ALL_AB_COL) to a CardAddressBook."""
        d = dict(zip(_ALL_COLS, row))
        return CardAddressBook(
            id=d["id"],
            key=d["key"],
            user_uid=d["user_uid"],
            is_default=bool(d["is_default"]),
            source_type=CardSourceType(d["source_type"]),
            name=d["name"],
            description=d["description"],
            ctag=d["ctag"],
            sync_config=d["sync_config"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def insert(self, book: CardAddressBook) -> CardAddressBook:
        """Persist a new address book and return it with id populated."""
        now = datetime.now(timezone.utc)
        book.created_at = now
        book.updated_at = now
        values = [[
            book.key,
            book.user_uid,
            book.is_default,
            book.source_type.value,
            book.name,
            book.description,
            book.ctag,
            book.sync_config,
            book.created_at,
            book.updated_at,
        ]]

        try:
            inserted = self._db.insert_in_table(
                table_name=tbl.TABLE_ADDRESSBOOK.name,
                column_tuple=_INSERT_COLS,
                values_tuple=values,
            )
        except BugException as exc:
            logger_contact.error("Unique violation inserting address book key=%s user=%s: %s", book.key, book.user_uid, exc)
            raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_DUPLICATE) from exc

        if inserted != 1:
            logger_contact.error("Address book insert affected %s rows instead of 1 (key=%s)", inserted, book.key)
            raise BugException("Address book insert did not affect exactly 1 row")

        fetched = self.find_by_key(book.user_uid, book.require_key)
        if fetched is None:
            raise BugException(f"Address book key={book.key} was inserted but could not be fetched back")
        return fetched

    def find_by_key(self, user_uid: str, key: str) -> CardAddressBook | None:
        """Return the address book matching (user_uid, key), or None if not found."""
        condition = AndCondition(
            EqualCondition(tbl.COL_AB_USER_UID.name, user_uid),
            EqualCondition(tbl.COL_AB_KEY.name, key),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_addressbook(rows[0])

    def find_by_key_only(self, key: str) -> CardAddressBook | None:
        """Return the address book matching key, regardless of owner.

        Unlike find_by_key, not scoped to a user_uid: used by the sharing feature, where the
        caller (a prospective sharee, or the share management module) does not necessarily own
        the address book. The key itself (an opaque generated uuid) is the lookup capability.
        """
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            column_tuple=_ALL_COLS,
            condition=EqualCondition(tbl.COL_AB_KEY.name, key),
            limit=1,
        ))
        if not rows:
            return None
        return self._row_to_addressbook(rows[0])

    def get_default_for_user(self, user_uid: str) -> CardAddressBook | None:
        """Return the default address book for user_uid, or None if not found."""
        condition = AndCondition(
            EqualCondition(tbl.COL_AB_USER_UID.name, user_uid),
            EqualCondition(tbl.COL_AB_IS_DEFAULT.name, True),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_addressbook(rows[0])

    def find_all(self, user_uid: str) -> list[CardAddressBook]:
        """Return all address books for the given user, ordered by id."""
        condition = EqualCondition(tbl.COL_AB_USER_UID.name, user_uid)
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            sort_by=tbl.COL_ID.name,
        )
        return [self._row_to_addressbook(row) for row in rows]

    def update(self, book: CardAddressBook) -> None:
        """Update all mutable columns of an existing address book. book.id must be set."""
        if book.id is None:
            raise BugException("RepositoryAddressBook.update called with book.id=None")

        book.updated_at = datetime.now(timezone.utc)
        update_cols = (
            tbl.COL_AB_NAME.name,
            tbl.COL_AB_DESCRIPTION.name,
            tbl.COL_AB_IS_DEFAULT.name,
            tbl.COL_AB_CTAG.name,
            tbl.COL_AB_SYNC_CONFIG.name,
            tbl.COL_AB_UPDATED_AT.name,
        )
        values = [
            book.name,
            book.description,
            book.is_default,
            book.ctag,
            book.sync_config,
            book.updated_at,
        ]

        updated = self._db.update_in_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            column_tuple=update_cols,
            values_list=values,
            condition=EqualCondition(tbl.COL_ID.name, book.id),
        )

        if updated == 0:
            logger_contact.error("Address book id=%s not found on update", book.id)
            raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)

    def clear_default(self, user_uid: str, exclude_id: int) -> None:
        """Set is_default=False on every address book of user_uid except exclude_id."""
        condition = AndCondition(
            EqualCondition(tbl.COL_AB_USER_UID.name, user_uid),
            NotEqualCondition(tbl.COL_ID.name, exclude_id),
        )
        self._db.update_in_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            column_tuple=(tbl.COL_AB_IS_DEFAULT.name,),
            values_list=[False],
            condition=condition,
        )

    def delete(self, book_id: int) -> None:
        """Physically delete an address book row. The caller must delete its contacts first."""
        deleted = self._db.delete_row_in_table(
            table_name=tbl.TABLE_ADDRESSBOOK.name,
            condition=EqualCondition(tbl.COL_ID.name, book_id),
            expected_row=1,
        )

        if deleted == 0:
            logger_contact.error("Address book id=%s not found on delete", book_id)
            raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
