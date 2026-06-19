from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.config.db.tables import (
    COL_FS_CONTENT_HASH,
    COL_FS_CONTENT_TYPE,
    COL_FS_CREATED_AT,
    COL_FS_DATA,
    COL_FS_KEY,
    COL_FS_SOURCE,
    COL_FS_UPDATED_AT,
    TABLE_FILE_STORAGE,
)
from app.utils.db.Condition import AndCondition, EqualCondition, LessOrEqualCondition

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


class DbFileStorage:
    """Generic binary blob store backed by the sogo6_file_storage table (key -> raw bytes + MIME).

    Knows nothing about its callers; the SQL client is injected.
    """

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    @staticmethod
    def _hash(data: bytes) -> str:
        """Return the sha256 hex digest used to compare payloads without loading them."""
        return hashlib.sha256(data).hexdigest()

    def write(self, key: str, data: bytes, content_type: str, source: str) -> None:
        """Persist a binary payload under a (fresh) key, with its owner source, MIME type and content hash."""
        now: datetime = datetime.now(timezone.utc)
        self._db.insert_in_table(
            table_name=TABLE_FILE_STORAGE.name,
            column_tuple=(COL_FS_KEY.name, COL_FS_SOURCE.name, COL_FS_DATA.name, COL_FS_CONTENT_TYPE.name,
                          COL_FS_CONTENT_HASH.name, COL_FS_CREATED_AT.name, COL_FS_UPDATED_AT.name),
            values_tuple=[[key, source, data, content_type, self._hash(data), now, now]],
        )

    def is_equal(self, key: str, data: bytes) -> bool:
        """Return True when the payload stored under key has the same content as data.

        Compares the stored sha256 against the hash of data, reading only the hash column - the
        blob itself is never loaded. False when the key is absent.
        """
        rows = list(self._db.select_from_table(
            table_name=TABLE_FILE_STORAGE.name,
            column_tuple=(COL_FS_CONTENT_HASH.name,),
            condition=EqualCondition(COL_FS_KEY.name, key),
            limit=1,
        ))
        return bool(rows) and rows[0][0] == self._hash(data)

    def read(self, key: str) -> tuple[bytes, str] | None:
        """Return the (bytes, content_type) stored under key, or None when absent."""
        rows = list(self._db.select_from_table(
            table_name=TABLE_FILE_STORAGE.name,
            column_tuple=(COL_FS_DATA.name, COL_FS_CONTENT_TYPE.name),
            condition=EqualCondition(COL_FS_KEY.name, key),
            limit=1,
        ))
        if not rows:
            return None
        data, content_type = rows[0]
        return bytes(data), content_type  # coerce a memoryview (PostgreSQL bytea) to bytes

    def delete(self, key: str) -> None:
        """Remove the payload stored under key (no-op when absent)."""
        self._db.delete_row_in_table(
            table_name=TABLE_FILE_STORAGE.name,
            condition=EqualCondition(COL_FS_KEY.name, key),
        )

    def all_keys(self, source: str) -> set[str]:
        """Return every key stored under `source` (used to detect blobs no owner references any more)."""
        rows = self._db.select_from_table(
            table_name=TABLE_FILE_STORAGE.name,
            column_tuple=(COL_FS_KEY.name,),
            condition=EqualCondition(COL_FS_SOURCE.name, source),
        )
        return {row[0] for row in rows}

    def purge_older_than(self, max_age_seconds: int, source: str) -> int:
        """Delete `source` blobs older than `max_age_seconds` (by created_at); return how many were removed."""
        cutoff: datetime = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        return self._db.delete_row_in_table(
            table_name=TABLE_FILE_STORAGE.name,
            condition=AndCondition(
                EqualCondition(COL_FS_SOURCE.name, source),
                LessOrEqualCondition(COL_FS_CREATED_AT.name, cutoff),
            ),
        )
