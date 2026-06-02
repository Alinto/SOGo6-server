"""Abstract contract for storing task results too large to fit in ``TaskState.result``.

Concrete backends live in their own modules (``TaskResultLargeStoreInMemory``,
``TaskResultLargeStoreFile``). The concrete instance is selected at call site via
``TaskResultLargeStoreFactory.get_large_store``, which reads
``TASK_RESULT_LARGE_STORAGE`` from ``AgentConst``.

Tasks put the dict returned by :meth:`save` into ``TaskState.result``; the
download endpoint resolves it back via :meth:`load`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TaskResultLargeStore(ABC):
    """Backend used to offload large task outputs out of ``TaskState.result``."""

    @abstractmethod
    def save(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Persist ``content`` and return a JSON-safe reference dict.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept alongside the content for the download path.
        :type content_type: str
        :return: reference dict the task puts under ``TaskState.result``; the dict
            always carries a ``storage`` key matching :class:`TaskResultLargeStorage`,
            plus backend-specific fields used by :meth:`load`.
        :rtype: dict[str, Any]
        """

    @abstractmethod
    def load(self, ref: dict[str, Any]) -> tuple[bytes, str]:
        """Resolve a reference produced by :meth:`save`.

        :param ref: dict the task wrote in ``TaskState.result``.
        :type ref: dict[str, Any]
        :return: ``(content_bytes, content_type)``.
        :rtype: tuple[bytes, str]
        :raises FileNotFoundError: the referenced content has expired or is missing.
        :raises ValueError: the ``storage`` field does not match this backend.
        """
