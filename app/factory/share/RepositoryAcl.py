from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.utils.db.Condition import AndCondition, EqualCondition
from app.utils.exceptions import BugException

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


# Columns in ALL_ACL_COL order (used for SELECT and row mapping)
_ALL_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_ACL_COL)
# Columns for INSERT - id is serial, omitted
_INSERT_COLS: tuple[str, ...] = tuple(col.name for col in tbl.ALL_ACL_COL if col.name != tbl.COL_ID.name)


class AclEntry:  # pylint: disable=too-few-public-methods
    """One row of sogo6_acl: the rights a single user has on a single resource."""

    def __init__(self, resource_type: str, key: str, owner: str, to_user: str, rights: dict) -> None:
        self.resource_type = resource_type
        self.key = key
        self.owner = owner
        self.to_user = to_user
        self.rights = rights


class RepositoryAcl:
    """Handles all DB reads and writes for sogo6_acl.

    Generic across resource types (calendar, addressbook, mail folder, ...): the caller always
    passes the ``resource_type`` discriminant (see :class:`app.factory.share.share.Share`).
    """

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    @staticmethod
    def _row_to_entry(row: tuple) -> AclEntry:
        d = dict(zip(_ALL_COLS, row))
        return AclEntry(
            resource_type=d["type"],
            key=d["key"],
            owner=d["owner"],
            to_user=d["to_user"],
            rights=d["rights"] or {},
        )

    def find_all_for_key(self, resource_type: str, key: str) -> list[AclEntry]:
        """Return every ACL entry (one per to_user) granted on a given resource."""
        condition = AndCondition(
            EqualCondition(tbl.COL_ACL_TYPE.name, resource_type),
            EqualCondition(tbl.COL_ACL_KEY.name, key),
        )
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_ACL.name,
            column_tuple=_ALL_COLS,
            condition=condition,
        )
        return [self._row_to_entry(row) for row in rows]

    def find_one(self, resource_type: str, key: str, to_user: str) -> AclEntry | None:
        """Return the ACL entry for a single (resource, to_user) pair, or None."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_ACL_TYPE.name, resource_type),
                EqualCondition(tbl.COL_ACL_KEY.name, key),
            ),
            EqualCondition(tbl.COL_ACL_TO_USER.name, to_user),
        )
        rows = list(self._db.select_from_table(
            table_name=tbl.TABLE_ACL.name,
            column_tuple=_ALL_COLS,
            condition=condition,
            limit=1,
        ))
        if not rows:
            return None
        return self._row_to_entry(rows[0])

    def find_all_for_to_user(self, resource_type: str, to_user: str) -> list[AclEntry]:
        """Return every resource key shared with to_user, for a given resource type."""
        condition = AndCondition(
            EqualCondition(tbl.COL_ACL_TYPE.name, resource_type),
            EqualCondition(tbl.COL_ACL_TO_USER.name, to_user),
        )
        rows = self._db.select_from_table(
            table_name=tbl.TABLE_ACL.name,
            column_tuple=_ALL_COLS,
            condition=condition,
        )
        return [self._row_to_entry(row) for row in rows]

    def upsert(self, entry: AclEntry) -> None:
        """Insert a new ACL entry, or update its rights if one already exists for (type, key, to_user)."""
        existing: AclEntry | None = self.find_one(entry.resource_type, entry.key, entry.to_user)
        if existing is None:
            self._db.insert_in_table(
                table_name=tbl.TABLE_ACL.name,
                column_tuple=_INSERT_COLS,
                values_tuple=[[entry.resource_type, entry.key, entry.owner, entry.to_user, entry.rights]],
            )
            return

        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_ACL_TYPE.name, entry.resource_type),
                EqualCondition(tbl.COL_ACL_KEY.name, entry.key),
            ),
            EqualCondition(tbl.COL_ACL_TO_USER.name, entry.to_user),
        )
        updated = self._db.update_in_table(
            table_name=tbl.TABLE_ACL.name,
            column_tuple=(tbl.COL_ACL_RIGHTS.name,),
            values_list=[entry.rights],
            condition=condition,
        )
        if updated == 0:
            raise BugException("RepositoryAcl.upsert: update matched 0 rows after existence check")

    def delete(self, resource_type: str, key: str, to_user: str) -> int:
        """Physically delete a single ACL entry. Returns the number of rows deleted (0 or 1)."""
        condition = AndCondition(
            AndCondition(
                EqualCondition(tbl.COL_ACL_TYPE.name, resource_type),
                EqualCondition(tbl.COL_ACL_KEY.name, key),
            ),
            EqualCondition(tbl.COL_ACL_TO_USER.name, to_user),
        )
        return self._db.delete_row_in_table(table_name=tbl.TABLE_ACL.name, condition=condition)

    def delete_all_for_key(self, resource_type: str, key: str) -> None:
        """Delete every ACL entry for a resource (used when the resource itself is deleted)."""
        condition = AndCondition(
            EqualCondition(tbl.COL_ACL_TYPE.name, resource_type),
            EqualCondition(tbl.COL_ACL_KEY.name, key),
        )
        self._db.delete_row_in_table(table_name=tbl.TABLE_ACL.name, condition=condition)
