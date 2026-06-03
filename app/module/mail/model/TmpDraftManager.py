from __future__ import annotations

import secrets
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from app.config.db.tables import (
    COL_DRAFT_KEY,
    COL_DRAFT_LOCK_STATE,
    COL_DRAFT_MAIL_SERVER_UID,
    COL_DRAFT_OWNER,
    TABLE_DRAFT_STATE,
)
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


class TmpDraftManager:
    """
    Manages the tmp_draft DB table (lookup, limit check, lock/unlock).
    """

    #: How long (seconds) to poll for an already-locked row before giving up.
    LOCK_POLL_TIMEOUT: float = 2.0
    #: Interval (seconds) between polling attempts.
    LOCK_POLL_INTERVAL: float = 0.1

    def __init__(self, db: ClientSQL, user_uid: str) -> None:
        self._db = db
        self._user_uid = user_uid

    def fetch_row(self, key: str) -> tuple[str, str, str, bool]:
        """Return ``(key, owner, mail_server_uid, locked)`` or raise 404."""
        rows = list(self._db.select_from_table(
            TABLE_DRAFT_STATE.name,
            (COL_DRAFT_KEY.name, COL_DRAFT_OWNER.name, COL_DRAFT_MAIL_SERVER_UID.name, COL_DRAFT_LOCK_STATE.name),
            EqualCondition(COL_DRAFT_KEY.name, key),
        ))
        if not rows:
            raise RequestException(err.ERROR_TMP_DRAFT_NOT_FOUND.m, error=err.ERROR_TMP_DRAFT_NOT_FOUND)
        return rows[0]  # type: ignore[return-value]

    def check_owner(self, row_owner: str) -> None:
        """Raise 403 if *row_owner* does not match the current user."""
        if row_owner != self._user_uid:
            raise RequestException(err.ERROR_TMP_DRAFT_OWNER_MISMATCH.m, error=err.ERROR_TMP_DRAFT_OWNER_MISMATCH)

    def wait_for_unlock(self, key: str) -> None:
        """Poll until the row is unlocked or raise 409 after timeout."""
        deadline = time.monotonic() + self.LOCK_POLL_TIMEOUT
        locked = True
        while locked and time.monotonic() < deadline:
            time.sleep(self.LOCK_POLL_INTERVAL)
            poll_rows = list(self._db.select_from_table(
                TABLE_DRAFT_STATE.name,
                (COL_DRAFT_LOCK_STATE.name,),
                EqualCondition(COL_DRAFT_KEY.name, key),
            ))
            locked = poll_rows[0][0] if poll_rows else True
        if locked:
            raise RequestException(err.ERROR_TMP_DRAFT_LOCKED.m, error=err.ERROR_TMP_DRAFT_LOCKED)

    def check_limit(self) -> None:
        """Raise 429 if the user has reached MAX_TMP_DRAFT drafts."""
        count = self._db.count_row_in_table(
            TABLE_DRAFT_STATE.name,
            EqualCondition(COL_DRAFT_OWNER.name, self._user_uid),
        )
        if count >= cs.MAX_TMP_DRAFT:
            raise RequestException(err.ERROR_TMP_DRAFT_LIMIT_REACHED.m, error=err.ERROR_TMP_DRAFT_LIMIT_REACHED)

    def generate_key(self) -> str:
        """Return a new random hex key (does **not** write to DB)."""
        return secrets.token_hex(cs.TMP_DRAFT_KEY_SIZE // 2)

    def lock_existing(self, key: str) -> None:
        """Set lock=True on an existing row; raise on unexpected update count."""
        updated = self._db.update_in_table(
            TABLE_DRAFT_STATE.name,
            (COL_DRAFT_LOCK_STATE.name,),
            [True],
            EqualCondition(COL_DRAFT_KEY.name, key),
        )
        if updated != 1:
            raise RequestException(err.ERROR_TMP_DRAFT_UPDATE_FAILED.m, error=err.ERROR_TMP_DRAFT_UPDATE_FAILED)

    def insert_locked(self, key: str) -> None:
        """Insert a new locked row (mail_server_uid = empty string)."""
        inserted = self._db.insert_in_table(
            TABLE_DRAFT_STATE.name,
            (COL_DRAFT_KEY.name, COL_DRAFT_OWNER.name, COL_DRAFT_MAIL_SERVER_UID.name, COL_DRAFT_LOCK_STATE.name),
            [[key, self._user_uid, "", True]],
        )
        if inserted != 1:
            raise RequestException(err.ERROR_TMP_DRAFT_INSERT_FAILED.m, error=err.ERROR_TMP_DRAFT_INSERT_FAILED)

    def unlock(self, key: str) -> None:
        """Set lock=False without changing mail_server_uid (used on error paths)."""
        self._db.update_in_table(
            TABLE_DRAFT_STATE.name,
            (COL_DRAFT_LOCK_STATE.name,),
            [False],
            EqualCondition(COL_DRAFT_KEY.name, key),
        )

    def release(self, key: str, new_mail_server_uid: str) -> None:
        """Update mail_server_uid and unlock the row atomically."""
        updated = self._db.update_in_table(
            TABLE_DRAFT_STATE.name,
            (COL_DRAFT_MAIL_SERVER_UID.name, COL_DRAFT_LOCK_STATE.name),
            [new_mail_server_uid, False],
            EqualCondition(COL_DRAFT_KEY.name, key),
        )
        if updated != 1:
            raise RequestException(err.ERROR_TMP_DRAFT_UPDATE_FAILED.m, error=err.ERROR_TMP_DRAFT_UPDATE_FAILED)

    def delete(self, key: str) -> None:
        """Delete the tmp_draft row identified by *key*.

        :param key: The tmp_draft key to delete.
        :type key: str
        :raises RequestException: If the deletion fails.
        """
        deleted = self._db.delete_row_in_table(
            TABLE_DRAFT_STATE.name,
            EqualCondition(COL_DRAFT_KEY.name, key),
            expected_row=1,
        )
        if deleted != 1:
            raise RequestException(err.ERROR_TMP_DRAFT_DELETE_FAILED.m, error=err.ERROR_TMP_DRAFT_DELETE_FAILED)



    def acquire(self, key: str | None, wait_if_locked: bool = False) -> tuple[str, str | None]:
        """Resolve or create a tmp_draft row and lock it.

        :param key: Existing tmp_draft key, or *None* to create a new one.
        :param wait_if_locked: If *True*, poll until the row is free before
            locking (used by ``upload_attachment``).  If *False*, raise
            immediately on a locked row (used by ``save_draft``).
        :return: ``(resolved_key, mail_server_uid)`` where *mail_server_uid*
            is *None* for brand-new rows (no IMAP draft yet).
        """
        if key is not None:
            _row_key, row_owner, row_mail_server_uid, row_locked = self.fetch_row(key)
            self.check_owner(row_owner)

            if row_locked:
                if wait_if_locked:
                    self.wait_for_unlock(key)
                else:
                    raise RequestException(err.ERROR_TMP_DRAFT_LOCKED.m, error=err.ERROR_TMP_DRAFT_LOCKED)

            mail_server_uid: str | None = row_mail_server_uid if row_mail_server_uid else None
            self.lock_existing(key)
            return key, mail_server_uid
        else:
            self.check_limit()
            new_key = self.generate_key()
            self.insert_locked(new_key)
            return new_key, None

    @contextmanager
    def locked(
        self,
        key: str | None,
        wait_if_locked: bool = False,
    ) -> Generator[tuple[str, str | None], None, None]:
        """Context manager that acquires (locks) a tmp_draft and unlocks on error.

        Yields ``(resolved_key, mail_server_uid)``.
        """
        resolved_key, mail_server_uid = self.acquire(key, wait_if_locked=wait_if_locked)
        try:
            yield resolved_key, mail_server_uid
        except Exception:
            self.unlock(resolved_key)
            raise
