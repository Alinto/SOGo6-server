"""Selects the concrete ``JobResultLargeStore`` backend.

Lives outside the ABC and its subclasses so it can import the concrete backends
at module level without the cycle the ABC would form (the subclasses import the
ABC to inherit from it).
"""
from __future__ import annotations

from typing import Any

from app.agent.AgentConst import JOB_RESULT_LARGE_STORAGE
from app.agent.jobs.job_result_large_store.JobResultLargeStorage import JobResultLargeStorage
from app.agent.jobs.job_result_large_store.JobResultLargeStoreFile import JobResultLargeStoreFile
from app.agent.jobs.job_result_large_store.JobResultLargeStoreInMemory import JobResultLargeStoreInMemory


class JobResultLargeStorageSelector:
    """Picks the right backend and runs the save / load, hiding it from callers."""

    @staticmethod
    def save(content: bytes, content_type: str) -> dict[str, Any]:
        """Store ``content`` in the backend set by ``JOB_RESULT_LARGE_STORAGE``.

        Write side: the backend is config-driven. The returned reference records
        which backend was used, so :meth:`load` can read it back regardless of a
        later config change.

        :return: reference dict to put under ``JobState.result``.
        """
        backend = (
            JobResultLargeStoreFile()
            if JOB_RESULT_LARGE_STORAGE == JobResultLargeStorage.FILE
            else JobResultLargeStoreInMemory()
        )
        return backend.save(content, content_type)

    @staticmethod
    def load(ref: dict[str, Any]) -> tuple[bytes, str]:
        """Read back a reference produced by :meth:`save`.

        Read side: the backend is chosen from ``ref["storage"]``, **not** from the
        current config — a result saved in one backend stays readable even if the
        default later changes, or if the worker and the API run with different
        settings.

        :param ref: reference dict produced by :meth:`save`.
        :return: ``(content_bytes, content_type)``.
        :raises ValueError: ``ref["storage"]`` matches no known backend.
        :raises FileNotFoundError: the referenced content has expired or is missing.
        """
        storage = ref.get("storage")
        if storage == JobResultLargeStorage.FILE.value:
            return JobResultLargeStoreFile().load(ref)
        if storage == JobResultLargeStorage.IN_MEMORY.value:
            return JobResultLargeStoreInMemory().load(ref)
        raise ValueError(f"Unknown large result storage: {storage!r}")
