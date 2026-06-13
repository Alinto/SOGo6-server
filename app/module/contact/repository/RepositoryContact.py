from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.serializer.ContactDeserializerDict import ContactDeserializerDict
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict
from app.utils import errors as err
from app.utils.calendar.DateTimeUtils import to_utc
from app.utils.db.Condition import AndCondition, EqualCondition, FullTextCondition
from app.utils.db.FullTextValue import FullTextValue
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_contact
from app.utils.maths.sogo_hash import generate_uuid
from app.utils.strings import strip_accents

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_CT_COL)
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_CT_COL if col.name != tbl.COL_ID.name)

_serializer = ContactSerializerDict()
_deserializer = ContactDeserializerDict()


class RepositoryContact:
    """Handles all DB reads and writes for sogo_contacts_contacts."""

    def __init__(self, db: ClientSQL) -> None:
        """Bind the repository to a SQL client."""
        self._db = db

    @staticmethod
    def _build_search_vector(contact: CardContact) -> str:
        """Build a plain-text, accent-insensitive search index from the contact's textual fields.

        The same normalization (strip_accents) is applied to the stored vector and to the query,
        so the match works regardless of the PostgreSQL text-search config or MariaDB collation.
        """
        parts: list[str] = [contact.display_name or ""]
        for value in (contact.first_name, contact.last_name, contact.nickname, contact.organization, contact.note):
            if value:
                parts.append(value)
        parts.extend(email.value for email in contact.emails)
        parts.extend(phone.number for phone in contact.phones)
        return strip_accents(" ".join(parts))

    @staticmethod
    def _row_to_contact(row: tuple) -> CardContact:
        """Map a DB row (ordered per ALL_CT_COL) to a CardContact.

        The full fiche is rebuilt from the JSON blob, then the relational columns (authoritative)
        override their blob counterparts.
        """
        d = dict(zip(_ALL_COLS, row))
        contact = _deserializer.deserialize(d[tbl.COL_CT_CONTACT_DATA.name])

        contact.db_id = d[tbl.COL_ID.name]
        contact.key = d[tbl.COL_CT_KEY.name]
        contact.addressbook_key = d[tbl.COL_CT_ADDRESSBOOK_KEY.name]
        contact.uid = d[tbl.COL_CT_UID.name]
        contact.kind = CardKind(d[tbl.COL_CT_KIND.name])
        contact.display_name = d[tbl.COL_CT_DISPLAY_NAME.name]
        contact.last_name = d[tbl.COL_CT_LAST_NAME.name]
        contact.first_name = d[tbl.COL_CT_FIRST_NAME.name]
        contact.organization = d[tbl.COL_CT_ORGANIZATION.name]
        contact.created_at = to_utc(d[tbl.COL_CT_CREATED_AT.name]) if d[tbl.COL_CT_CREATED_AT.name] is not None else None
        contact.updated_at = to_utc(d[tbl.COL_CT_UPDATED_AT.name]) if d[tbl.COL_CT_UPDATED_AT.name] is not None else None
        return contact

    def insert(self, contact: CardContact) -> CardContact:
        """Persist a new contact and return it with id and key populated."""
        now = datetime.now(timezone.utc)
        contact.key = generate_uuid()
        contact.created_at = now
        contact.updated_at = now

        values = [[
            contact.key,
            contact.addressbook_key,
            contact.uid,
            contact.kind.value,
            contact.last_name,
            contact.first_name,
            contact.organization,
            contact.display_name,
            False,
            FullTextValue(RepositoryContact._build_search_vector(contact)),
            _serializer.serialize(contact),
            contact.created_at,
            contact.updated_at,
        ]]

        try:
            inserted = self._db.insert_in_table(
                table_name=tbl.TABLE_CONTACT.name,
                column_tuple=_INSERT_COLS,
                values_tuple=values,
            )
        except BugException as exc:
            logger_contact.error("Unique violation inserting contact uid=%s book=%s: %s", contact.uid, contact.addressbook_key, exc)
            raise RequestException(error=err.ERROR_CONTACT_DUPLICATE) from exc

        if inserted != 1:
            logger_contact.error("Contact insert affected %s rows instead of 1 (uid=%s)", inserted, contact.uid)
            raise BugException("Contact insert did not affect exactly 1 row")

        fetched = self.find_by_key(contact.require_addressbook_key, contact.require_key)
        if fetched is None:
            raise BugException(f"Contact key={contact.key} was inserted but could not be fetched back")
        return fetched

    def update(self, contact: CardContact) -> None:
        """Update an existing contact. contact.db_id must be set."""
        if contact.db_id is None:
            raise BugException("RepositoryContact.update called with contact.db_id=None")

        contact.updated_at = datetime.now(timezone.utc)
        update_cols = (
            tbl.COL_CT_UID.name,
            tbl.COL_CT_KIND.name,
            tbl.COL_CT_LAST_NAME.name,
            tbl.COL_CT_FIRST_NAME.name,
            tbl.COL_CT_ORGANIZATION.name,
            tbl.COL_CT_DISPLAY_NAME.name,
            tbl.COL_CT_SEARCH_VECTOR.name,
            tbl.COL_CT_CONTACT_DATA.name,
            tbl.COL_CT_UPDATED_AT.name,
        )
        values = [
            contact.uid,
            contact.kind.value,
            contact.last_name,
            contact.first_name,
            contact.organization,
            contact.display_name,
            FullTextValue(RepositoryContact._build_search_vector(contact)),
            _serializer.serialize(contact),
            contact.updated_at,
        ]

        updated = self._db.update_in_table(
            table_name=tbl.TABLE_CONTACT.name,
            column_tuple=update_cols,
            values_list=values,
            condition=EqualCondition(tbl.COL_ID.name, contact.db_id),
        )

        if updated == 0:
            logger_contact.error("Contact db_id=%s not found on update", contact.db_id)
            raise RequestException(error=err.ERROR_CONTACT_NOT_FOUND)

    def find_by_key(self, addressbook_key: str, key: str) -> CardContact | None:
        """Return a single contact by key within the given address book, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_CT_KEY.name, key),
                EqualCondition(tbl.COL_CT_ADDRESSBOOK_KEY.name, addressbook_key),
            ),
            EqualCondition(tbl.COL_CT_IS_DELETED.name, False),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_contact(rows[0])

    def find_by_uid(self, addressbook_key: str, uid: str) -> CardContact | None:
        """Return a single contact by vCard UID within the given address book, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_CT_UID.name, uid),
                EqualCondition(tbl.COL_CT_ADDRESSBOOK_KEY.name, addressbook_key),
            ),
            EqualCondition(tbl.COL_CT_IS_DELETED.name, False),
        )
        # pylint: disable=duplicate-code
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        # pylint: enable=duplicate-code
        if not rows:
            return None
        return self._row_to_contact(rows[0])

    def find_by_addressbook(
        self,
        addressbook_key: str,
        search: str | None = None,
        offset: int = 0,
        limit: int = 0,
        sort_by: str = tbl.COL_CT_DISPLAY_NAME.name,
    ) -> list[CardContact]:
        """Return non-deleted contacts of an address book, paginated and sorted.

        When search is provided, a full-text filter is applied against the search_vector column
        (token match via the database full-text index, not a substring match) and results are
        ordered by relevance first, then by sort_by as a tiebreaker.
        """
        condition = AndCondition(
            EqualCondition(tbl.COL_CT_ADDRESSBOOK_KEY.name, addressbook_key),
            EqualCondition(tbl.COL_CT_IS_DELETED.name, False),
        )
        search_condition = (
            FullTextCondition(tbl.COL_CT_SEARCH_VECTOR.name, strip_accents(search))
            if search else None
        )
        if search_condition is not None:
            condition = AndCondition(condition, search_condition)
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            rank_by=search_condition,
        )
        return [self._row_to_contact(row) for row in rows]

    def count_by_addressbook(self, addressbook_key: str, search: str | None = None) -> int:
        """Return the number of non-deleted contacts in an address book (for pagination total)."""
        condition = AndCondition(
            EqualCondition(tbl.COL_CT_ADDRESSBOOK_KEY.name, addressbook_key),
            EqualCondition(tbl.COL_CT_IS_DELETED.name, False),
        )
        if search:
            condition = AndCondition(condition, FullTextCondition(tbl.COL_CT_SEARCH_VECTOR.name, strip_accents(search)))
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_CONTACT.name,
            column_tuple=(tbl.COL_CT_KEY.name,),
            condition=condition,
        )
        return sum(1 for _ in rows)

    def delete_by_key(self, addressbook_key: str, key: str, hard_delete: bool = False) -> None:
        """Soft-delete (or hard-delete) a single contact row by its opaque key."""
        condition = AndCondition(
            EqualCondition(tbl.COL_CT_KEY.name, key),
            EqualCondition(tbl.COL_CT_ADDRESSBOOK_KEY.name, addressbook_key),
        )
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_CONTACT.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_CONTACT.name,
                column_tuple=(tbl.COL_CT_IS_DELETED.name, tbl.COL_CT_UPDATED_AT.name),
                values_list=[True, now],
                condition=condition,
            )

    def delete_all(self, addressbook_key: str, hard_delete: bool = False) -> None:
        """Soft-delete (or hard-delete) all contacts belonging to an address book."""
        condition = EqualCondition(tbl.COL_CT_ADDRESSBOOK_KEY.name, addressbook_key)
        if hard_delete:
            self._db.delete_row_in_table(table_name=tbl.TABLE_CONTACT.name, condition=condition)
        else:
            now: datetime = datetime.now(timezone.utc)
            self._db.update_in_table(
                table_name=tbl.TABLE_CONTACT.name,
                column_tuple=(tbl.COL_CT_IS_DELETED.name, tbl.COL_CT_UPDATED_AT.name),
                values_list=[True, now],
                condition=condition,
            )
