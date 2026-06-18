from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.contact.model.CardList import CardList
from app.utils import errors as err
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.db.Condition import AndCondition, Condition, EqualCondition, LikeCondition, Order, TrueCondition
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_contact
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_LST_COL)
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_LST_COL if col.name != tbl.COL_ID.name)
_MEMBER_COLS: tuple[str, ...] = (tbl.COL_LM_LIST_KEY.name, tbl.COL_LM_CONTACT_KEY.name)


class RepositoryContactList:
    """Handles all DB reads and writes for sogo_contacts_lists and its sogo_contacts_list_members join.

    The list row and its membership are two separate concerns: row CRUD never touches the join,
    member management is exposed through the dedicated member methods. The module orchestrates both.
    """

    def __init__(self, db: ClientSQL) -> None:
        """Bind the repository to a SQL client."""
        self._db = db

    @staticmethod
    def _row_to_list(row: tuple) -> CardList:
        """Map a DB row (ordered per ALL_LST_COL) to a CardList. Members are not populated here."""
        d = dict(zip(_ALL_COLS, row))
        return CardList(
            id=d[tbl.COL_ID.name],
            key=d[tbl.COL_LST_KEY.name],
            addressbook_key=d[tbl.COL_LST_ADDRESSBOOK_KEY.name],
            uid=d[tbl.COL_LST_UID.name],
            name=d[tbl.COL_LST_NAME.name],
            description=d[tbl.COL_LST_DESCRIPTION.name],
            is_deleted=bool(d[tbl.COL_LST_IS_DELETED.name]),
            created_at=to_utc(d[tbl.COL_LST_CREATED_AT.name]) if d[tbl.COL_LST_CREATED_AT.name] is not None else None,
            updated_at=to_utc(d[tbl.COL_LST_UPDATED_AT.name]) if d[tbl.COL_LST_UPDATED_AT.name] is not None else None,
        )

    def insert(self, card_list: CardList) -> CardList:
        """Persist a new list row (members excluded) and return it with id and key populated."""
        now = datetime.now(timezone.utc)
        card_list.key = generate_uuid()
        card_list.created_at = now
        card_list.updated_at = now
        values = [[
            card_list.key,
            card_list.addressbook_key,
            card_list.uid,
            card_list.name,
            card_list.description,
            False,
            card_list.created_at,
            card_list.updated_at,
        ]]

        try:
            inserted = self._db.insert_in_table(
                table_name=tbl.TABLE_CONTACT_LIST.name,
                column_tuple=_INSERT_COLS,
                values_tuple=values,
            )
        except BugException as exc:
            logger_contact.error("Unique violation inserting list uid=%s book=%s: %s", card_list.uid, card_list.addressbook_key, exc)
            raise RequestException(error=err.ERROR_CONTACT_LIST_DUPLICATE) from exc

        if inserted != 1:
            logger_contact.error("List insert affected %s rows instead of 1 (uid=%s)", inserted, card_list.uid)
            raise BugException("List insert did not affect exactly 1 row")

        fetched = self.find_by_key(card_list.require_addressbook_key, card_list.require_key)
        if fetched is None:
            raise BugException(f"List key={card_list.key} was inserted but could not be fetched back")
        return fetched

    def update(self, card_list: CardList) -> None:
        """Update the mutable columns of an existing list row (members excluded). card_list.db_id must be set."""
        if card_list.id is None:
            raise BugException("RepositoryContactList.update called with card_list.id=None")

        card_list.updated_at = datetime.now(timezone.utc)
        update_cols = (
            tbl.COL_LST_NAME.name,
            tbl.COL_LST_DESCRIPTION.name,
            tbl.COL_LST_UPDATED_AT.name,
        )
        values = [
            card_list.name,
            card_list.description,
            card_list.updated_at,
        ]

        updated = self._db.update_in_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            column_tuple=update_cols,
            values_list=values,
            condition=EqualCondition(tbl.COL_ID.name, card_list.id),
        )

        if updated == 0:
            logger_contact.error("List id=%s not found on update", card_list.id)
            raise RequestException(error=err.ERROR_CONTACT_LIST_NOT_FOUND)

    def find_by_key(self, addressbook_key: str, key: str) -> CardList | None:
        """Return a single non-deleted list by key within the given address book, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_LST_KEY.name, key),
                EqualCondition(tbl.COL_LST_ADDRESSBOOK_KEY.name, addressbook_key),
            ),
            EqualCondition(tbl.COL_LST_IS_DELETED.name, False),
        )
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        if not rows:
            return None
        return self._row_to_list(rows[0])

    def find_by_uid(self, addressbook_key: str, uid: str) -> CardList | None:
        """Return a single non-deleted list by uid within the given address book, or None (import dedup)."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_LST_UID.name, uid),
                EqualCondition(tbl.COL_LST_ADDRESSBOOK_KEY.name, addressbook_key),
            ),
            EqualCondition(tbl.COL_LST_IS_DELETED.name, False),
        )
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        if not rows:
            return None
        return self._row_to_list(rows[0])

    def find_by_addressbook(
        self,
        addressbook_key: str,
        search: str | None = None,
        offset: int = 0,
        limit: int = 0,
        sort_by: str = tbl.COL_LST_NAME.name,
        order: Order = Order.ASC,
    ) -> list[CardList]:
        """Return non-deleted lists of an address book, paginated and sorted.

        When search is provided, a case-insensitive name substring filter is applied (lists have no
        full-text vector; the set per book is small).
        """
        # pylint: disable=duplicate-code
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            column_tuple=_ALL_COLS,
            condition=self._book_filter(addressbook_key, search),
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            order=order,
        )
        # pylint: enable=duplicate-code
        return [self._row_to_list(row) for row in rows]

    def count_by_addressbook(self, addressbook_key: str, search: str | None = None) -> int:
        """Return the number of non-deleted lists in an address book (for pagination total)."""
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            column_tuple=(tbl.COL_LST_KEY.name,),
            condition=self._book_filter(addressbook_key, search),
        )
        return sum(1 for _ in rows)

    @staticmethod
    def _book_filter(addressbook_key: str, search: str | None) -> Condition:
        """Build the non-deleted-lists-of-a-book condition, with an optional name substring filter."""
        condition: Condition = AndCondition(
            EqualCondition(tbl.COL_LST_ADDRESSBOOK_KEY.name, addressbook_key),
            EqualCondition(tbl.COL_LST_IS_DELETED.name, False),
        )
        if search:
            condition = AndCondition(condition, LikeCondition(tbl.COL_LST_NAME.name, f"%{search}%"))
        return condition

    def delete_by_key(self, addressbook_key: str, key: str, hard_delete: bool = False) -> None:
        """Soft-delete (or hard-delete) a single list row by its opaque key. The caller clears members."""
        condition = AndCondition(
            EqualCondition(tbl.COL_LST_KEY.name, key),
            EqualCondition(tbl.COL_LST_ADDRESSBOOK_KEY.name, addressbook_key),
        )
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_CONTACT_LIST.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_CONTACT_LIST.name,
                column_tuple=(tbl.COL_LST_IS_DELETED.name, tbl.COL_LST_UPDATED_AT.name),
                values_list=[True, now],
                condition=condition,
            )

    def delete_all(self, addressbook_key: str, hard_delete: bool = False) -> None:
        """Remove all lists of an address book, physically or as detached tombstones.

        Soft delete (the default) marks every list is_deleted and detaches it from the book by
        clearing addressbook_key, mirroring the contact tombstone behaviour on book deletion.
        """
        condition = EqualCondition(tbl.COL_LST_ADDRESSBOOK_KEY.name, addressbook_key)
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_CONTACT_LIST.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_CONTACT_LIST.name,
                column_tuple=(tbl.COL_LST_IS_DELETED.name, tbl.COL_LST_ADDRESSBOOK_KEY.name, tbl.COL_LST_UPDATED_AT.name),
                values_list=[True, None, now],
                condition=condition,
            )

    def purge_deleted(self) -> int:
        """Physically remove every soft-deleted list row (is_deleted = True), returning the count purged."""
        return self._db.delete_row_in_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            condition=EqualCondition(tbl.COL_LST_IS_DELETED.name, True),
        )

    def all_keys(self) -> set[str]:
        """Return the opaque keys of every list row still present (used for orphan detection)."""
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST.name,
            column_tuple=(tbl.COL_LST_KEY.name,),
            condition=TrueCondition(),
        )
        return {row[0] for row in rows}

    #
    # Membership (sogo_contacts_list_members join)
    #
    def find_member_keys(self, list_key: str) -> list[str]:
        """Return the contact keys of a list's members, in insertion order."""
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
            column_tuple=(tbl.COL_LM_CONTACT_KEY.name,),
            condition=EqualCondition(tbl.COL_LM_LIST_KEY.name, list_key),
        )
        return [row[0] for row in rows]

    def replace_members(self, list_key: str, contact_keys: list[str]) -> None:
        """Replace a list's membership with the given contact keys (full rewrite of the join rows)."""
        self.delete_members(list_key)
        unique_keys: list[str] = list(dict.fromkeys(contact_keys))
        if not unique_keys:
            return
        values = [[list_key, contact_key] for contact_key in unique_keys]
        self._db.insert_in_table(
            table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
            column_tuple=_MEMBER_COLS,
            values_tuple=values,
        )

    def delete_members(self, list_key: str) -> None:
        """Remove every member join row of a list."""
        self._db.delete_row_in_table(
            table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
            condition=EqualCondition(tbl.COL_LM_LIST_KEY.name, list_key),
        )

    def remove_contact_from_lists(self, contact_key: str) -> None:
        """Remove a contact from every list it belongs to (called when the contact is deleted)."""
        self._db.delete_row_in_table(
            table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
            condition=EqualCondition(tbl.COL_LM_CONTACT_KEY.name, contact_key),
        )

    def purge_orphan_members(self, live_list_keys: set[str], live_contact_keys: set[str]) -> int:
        """Remove member rows pointing at a vanished list or contact, returning the count removed.

        Called by the maintenance clean() once list and contact tombstones have been physically
        purged: a membership row whose list_key or contact_key no longer resolves to an existing row
        is dropped. The live key sets are supplied by the caller (the contact keys come from another
        repository, so this method never reaches outside its own join table).
        """
        member_pairs: list[tuple] = list(self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
            column_tuple=_MEMBER_COLS,
            condition=TrueCondition(),
        ))
        orphan_list_keys: set[str] = {lk for lk, _ in member_pairs if lk not in live_list_keys}
        orphan_contact_keys: set[str] = {ck for _, ck in member_pairs if ck not in live_contact_keys}
        removed: int = 0
        for list_key in orphan_list_keys:
            removed += self._db.delete_row_in_table(
                table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
                condition=EqualCondition(tbl.COL_LM_LIST_KEY.name, list_key),
            )
        for contact_key in orphan_contact_keys:
            removed += self._db.delete_row_in_table(
                table_name=tbl.TABLE_CONTACT_LIST_MEMBER.name,
                condition=EqualCondition(tbl.COL_LM_CONTACT_KEY.name, contact_key),
            )
        return removed
