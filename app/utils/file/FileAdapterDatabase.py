from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils.file.FileAdapter import FileAdapter
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.manager.db.DbFileStorage import DbFileStorage


class FileAdapterDatabase(FileAdapter):
    """FileAdapter backed by the database blob store (sogo_file_storage)."""

    def __init__(self, storage: DbFileStorage) -> None:
        self._storage: DbFileStorage = storage

    def save(self, data: bytes, content_type: str) -> str:
        key: str = generate_uuid()
        self._storage.write(key, data, content_type)
        return self._make_reference(key)

    def load(self, ref: str) -> tuple[bytes, str] | None:
        if not self.is_reference(ref):
            return None
        return self._storage.read(self._reference_key(ref))

    def matches(self, ref: str, data: bytes) -> bool:
        return self.is_reference(ref) and self._storage.is_equal(self._reference_key(ref), data)

    def delete(self, ref: str) -> None:
        if self.is_reference(ref):
            self._storage.delete(self._reference_key(ref))

    def _all_references(self) -> set[str]:
        return {self._make_reference(key) for key in self._storage.all_keys()}
