"""Abstract contract for storing job results too large to fit in ``JobState.result``.

Concrete backends live in their own modules (``JobResultLargeStoreInMemory``,
``JobResultLargeStoreFile``).

- Write side: :meth:`get` returns the backend configured via
  ``JOB_RESULT_LARGE_STORAGE`` in ``AgentConst``; a job calls ``.save(...)`` on it.
- Read side: :meth:`load_ref` resolves a reference using the backend that
  produced it (``ref["storage"]``), independent of the current config.

Jobs put the dict returned by :meth:`save` into ``JobState.result``; the
download endpoint resolves it back via :meth:`load_ref`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.agent.AgentConst import JOB_RESULT_LARGE_STORAGE
from app.agent.jobs.job_result_large_store.JobResultLargeStorage import JobResultLargeStorage


class JobResultLargeStore(ABC):
    """Backend used to offload large job outputs out of ``JobState.result``."""

    @staticmethod
    def get() -> "JobResultLargeStore":
        """Return the backend matching ``JOB_RESULT_LARGE_STORAGE`` (write side).

        Used by jobs to **save** a new result. Stores are stateless, so
        instantiating one per call is cheap. The concrete subclasses are
        imported here, not at module level, to avoid the cycle they would form
        by importing this base class.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import
        from app.agent.jobs.job_result_large_store.JobResultLargeStoreFile import JobResultLargeStoreFile
        from app.agent.jobs.job_result_large_store.JobResultLargeStoreInMemory import JobResultLargeStoreInMemory
        if JOB_RESULT_LARGE_STORAGE == JobResultLargeStorage.FILE:
            return JobResultLargeStoreFile()
        return JobResultLargeStoreInMemory()

    @staticmethod
    def load_ref(ref: dict[str, Any]) -> tuple[bytes, str]:
        """Resolve a reference using the backend that produced it (read side).

        The backend is chosen from ``ref["storage"]``, **not** from the current
        ``JOB_RESULT_LARGE_STORAGE`` config: a result saved in one backend must
        stay readable even if the configured default later changes, or if the
        worker and the API run with different settings.

        :param ref: reference dict produced by :meth:`save`.
        :return: ``(content_bytes, content_type)``.
        :raises ValueError: ``ref["storage"]`` matches no known backend.
        :raises FileNotFoundError: the referenced content has expired or is missing.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import
        from app.agent.jobs.job_result_large_store.JobResultLargeStoreFile import JobResultLargeStoreFile
        from app.agent.jobs.job_result_large_store.JobResultLargeStoreInMemory import JobResultLargeStoreInMemory
        storage = ref.get("storage")
        if storage == JobResultLargeStorage.FILE.value:
            return JobResultLargeStoreFile().load(ref)
        if storage == JobResultLargeStorage.IN_MEMORY.value:
            return JobResultLargeStoreInMemory().load(ref)
        raise ValueError(f"Unknown large result storage: {storage!r}")

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
