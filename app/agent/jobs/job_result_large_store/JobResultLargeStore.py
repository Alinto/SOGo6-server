"""Abstract contract for storing job results too large to fit in ``JobState.result``.

Concrete backends live in their own modules (``JobResultLargeStoreInMemory``,
``JobResultLargeStoreFile``). Callers don't pick a backend directly — they go
through ``JobResultLargeStorageSelector``: ``save()`` (write side, config-driven)
and ``load()`` (read side, driven by ``ref["storage"]``).

Jobs put the dict returned by ``save`` into ``JobState.result``; the download
endpoint resolves it back via ``JobResultLargeStorageSelector.load``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JobResultLargeStore(ABC):
    """Backend used to offload large job outputs out of ``JobState.result``."""

    @abstractmethod
    def save(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Persist ``content`` and return a JSON-safe reference dict.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept alongside the content for the download path.
        :type content_type: str
        :return: reference dict the job puts under ``JobState.result``; the dict
            always carries a ``storage`` key matching :class:`JobResultLargeStorage`,
            plus backend-specific fields used by :meth:`load`.
        :rtype: dict[str, Any]
        """

    @abstractmethod
    def load(self, ref: dict[str, Any]) -> tuple[bytes, str]:
        """Resolve a reference produced by :meth:`save`.

        :param ref: dict the job wrote in ``JobState.result``.
        :type ref: dict[str, Any]
        :return: ``(content_bytes, content_type)``.
        :rtype: tuple[bytes, str]
        :raises FileNotFoundError: the referenced content has expired or is missing.
        :raises ValueError: the ``storage`` field does not match this backend.
        """
