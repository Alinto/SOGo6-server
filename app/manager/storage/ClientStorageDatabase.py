from __future__ import annotations

from typing import Callable, TypeVar, TYPE_CHECKING

from app.manager.storage.ClientStorage import ClientStorage
from app.manager.storage.DbFileStorage import DbFileStorage
from app.utils.maths.sogo_hash import generate_uuid
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL
    from app.manager.storage.StorageSource import StorageSource

T = TypeVar("T")


class ClientStorageDatabase(ClientStorage):
    """ClientStorage backed by the database blob store (sogo6_file_storage), scoped to one owner source.

    Connection handling depends on how it is built:
    - given a live ``db``, it reuses that connection and never closes it (the owner does);
    - given no ``db``, it opens a short-lived connection for each operation and closes it right after.
    The second mode lets a long-lived holder (the Agent singleton) expose the store without ever
    keeping a connection open - which would otherwise be inherited across the worker fork.
    """

    def __init__(
        self, process_setting: ProcessSetting, source: StorageSource, db: ClientSQL | None = None,
    ) -> None:
        super().__init__(source)
        self._process_setting: ProcessSetting = process_setting
        self._db: ClientSQL | None = db

    def save(self, data: bytes, content_type: str) -> str:
        key: str = generate_uuid()
        self._run(lambda storage: storage.write(key, data, content_type, self._source))
        return self._make_reference(key)

    def load(self, ref: str) -> tuple[bytes, str] | None:
        if not self.is_reference(ref):
            return None
        return self._run(lambda storage: storage.read(self._reference_key(ref)))

    def matches(self, ref: str, data: bytes) -> bool:
        return self.is_reference(ref) and self._run(
            lambda storage: storage.is_equal(self._reference_key(ref), data),
        )

    def delete(self, ref: str) -> None:
        if self.is_reference(ref):
            self._run(lambda storage: storage.delete(self._reference_key(ref)))

    def _all_references(self) -> set[str]:
        keys: set[str] = self._run(lambda storage: storage.all_keys(self._source))
        return {self._make_reference(key) for key in keys}

    def purge_older_than(self, max_age_seconds: int) -> int:
        return self._run(lambda storage: storage.purge_older_than(max_age_seconds, self._source))

    def _run(self, op: Callable[[DbFileStorage], T]) -> T:
        """Run op on a DbFileStorage, opening/closing a connection only when none was injected."""
        if self._db is not None:
            return op(DbFileStorage(self._db))
        db: ClientSQL = self._connect()
        try:
            return op(DbFileStorage(db))
        finally:
            db.close()

    def _connect(self) -> ClientSQL:
        db: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=f"Client{self._process_setting.SOGO_P_DB_TYPE}",
            module_args=self._process_setting.get_db_settings(),
        )
        db.connect()
        return db
