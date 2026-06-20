from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.media.MediaType import MediaType
from app.utils.uri.DataUri import DataUri

if TYPE_CHECKING:
    from app.manager.storage.StorageSource import StorageSource


class ClientStorage(ABC):
    """Swappable store for inline binary files, kept behind opaque sogo:file:<key> references.

    The shared list-level policy (save_all/load_all/purge_orphans) offloads inline data URIs,
    deduplicates by content and reclaims orphans; subclasses implement the per-item primitives
    (save/load/matches/delete) over a concrete backend (database now, file share or WebDAV later).
    Each instance is scoped to one owner source so co-located uses of the same store stay isolated.
    """

    REFERENCE_PREFIX: str = "sogo:file:"

    def __init__(self, source: StorageSource) -> None:
        self._source: StorageSource = source

    @staticmethod
    def is_reference(value: str) -> bool:
        """Return True when value is a managed reference rather than an external URI."""
        return value.startswith(ClientStorage.REFERENCE_PREFIX)

    @classmethod
    def _make_reference(cls, key: str) -> str:
        return f"{cls.REFERENCE_PREFIX}{key}"

    @classmethod
    def _reference_key(cls, ref: str) -> str:
        return ref[len(cls.REFERENCE_PREFIX):]

    def save_all(self, previous: list[str], incoming: list[str],
                 max_size_bytes: int, allowed_types: frozenset[str]) -> list[str]:
        """Validate and offload a list of file values, returning their stored form.

        Each inline payload is saved under its sniffed type, never the caller-declared one, so a
        polyglot cannot be echoed back with an executable content type. An unchanged payload (matched
        by content) reuses its reference, an http(s) URI passes through. Nothing is deleted here:
        dropped references become orphans for purge_orphans, so save_all never mutates the store
        before the owning row is committed.

        :raises RequestException: ERROR_FILE_TOO_LARGE / ERROR_FILE_TYPE_NOT_ALLOWED.
        """
        decoded: dict[int, tuple[bytes, str]] = self._decode_inline(incoming, max_size_bytes, allowed_types)
        own_references: list[str] = [value for value in previous if self.is_reference(value)]
        reused: set[str] = set()
        stored: list[str] = []
        for index, value in enumerate(incoming):
            if self.is_reference(value):
                if value in own_references:
                    stored.append(value)
                    reused.add(value)
                continue
            if index not in decoded:
                stored.append(value)  # validated http(s) URI, kept as-is
                continue
            data, content_type = decoded[index]
            match: str | None = next(
                (ref for ref in own_references if ref not in reused and self.matches(ref, data)), None,
            )
            if match is not None:
                stored.append(match)
                reused.add(match)
            else:
                stored.append(self.save(data, content_type))
        return stored

    @staticmethod
    def _decode_inline(values: list[str], max_size_bytes: int,
                       allowed_types: frozenset[str]) -> dict[int, tuple[bytes, str]]:
        """Decode and check each inline payload once (size + sniffed type), keyed by its index.

        References are skipped; any non-data value must be an http(s) URI - a malformed data URI or a
        non-http scheme (javascript:, data:text/html) is rejected so it can never be stored and echoed.
        """
        decoded: dict[int, tuple[bytes, str]] = {}
        for index, value in enumerate(values):
            if ClientStorage.is_reference(value):
                continue
            parsed: tuple[str, bytes] | None = DataUri.parse(value)
            if parsed is None:
                if not value.startswith(("http://", "https://")):
                    raise RequestException(error=err.ERROR_FILE_TYPE_NOT_ALLOWED)
                continue  # external http(s) URI, kept as-is
            data: bytes = parsed[1]
            if len(data) > max_size_bytes:
                raise RequestException(error=err.ERROR_FILE_TOO_LARGE)
            sniffed: str | None = MediaType.get_content_type(data)
            if sniffed is None or sniffed not in allowed_types:
                raise RequestException(error=err.ERROR_FILE_TYPE_NOT_ALLOWED)
            decoded[index] = (data, sniffed)
        return decoded

    def load_all(self, values: list[str]) -> list[str]:
        """Turn managed references back into inline data URIs; pass URIs through.

        Outbound counterpart of save_all. A reference whose payload no longer loads (its blob was
        purged) is dropped rather than leaked.
        """
        loaded: list[str] = []
        for value in values:
            if not self.is_reference(value):
                loaded.append(value)
                continue
            payload: tuple[bytes, str] | None = self.load(value)
            if payload is not None:
                data, content_type = payload
                loaded.append(DataUri.build(content_type, data))
        return loaded

    def purge_orphans(self, referenced: set[str]) -> int:
        """Delete every stored payload whose reference is not in `referenced`; returns the count removed."""
        orphans: set[str] = self._all_references() - referenced
        for reference in orphans:
            self.delete(reference)
        return len(orphans)

    @abstractmethod
    def purge_older_than(self, max_age_seconds: int) -> int:
        """Delete this owner's blobs older than `max_age_seconds`; returns the count removed."""

    @abstractmethod
    def save(self, data: bytes, content_type: str) -> str:
        """Persist a binary payload and return its managed reference."""

    @abstractmethod
    def load(self, ref: str) -> tuple[bytes, str] | None:
        """Return the (bytes, content_type) behind a reference, or None when absent."""

    @abstractmethod
    def matches(self, ref: str, data: bytes) -> bool:
        """Return True when the payload behind a reference has the same content as data.

        Lets a caller detect an unchanged payload without loading it; a backend answers from a
        stored hash (database) or an entity tag (WebDAV) rather than fetching the bytes.
        """

    @abstractmethod
    def delete(self, ref: str) -> None:
        """Remove the payload behind a reference (no-op when absent)."""

    @abstractmethod
    def _all_references(self) -> set[str]:
        """Every reference currently stored (backend enumeration used by the orphan purge)."""
