"""Abstract storage service for blobs too big to ride inside a payload / result.

A broker must not carry large binaries (message bloat, Redis memory). Blobs that
do not fit a payload/result are offloaded here. Used in both directions:

- **output** - a worker ``save()`` s a large result and stores the returned
  :class:`JobLargeRef` (via ``to_dict``) under ``JobState.result``; the download
  endpoint ``load()`` s it back.
- **input** - the API ``save()`` s a large uploaded file and stores the reference
  in the ``JobRequest`` payload; the worker ``load()`` s it then ``delete()`` s it
  once consumed.

The concrete backend is process-wide and stateless: a single instance is built
once from config by ``ClientAgent`` and reused. Backends never appear in the
serialised reference - the reader uses the same configured backend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef


class JobLargeStore(ABC):
    """Backend that offloads large job inputs / outputs out of payload and result."""

    @abstractmethod
    def save(self, content: bytes, content_type: str) -> JobLargeRef:
        """Persist ``content`` and return a reference to it.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept on the reference for the read path.
        :type content_type: str
        :return: a reference to put on the wire (payload or result).
        :rtype: JobLargeRef
        """

    @abstractmethod
    def load(self, ref: JobLargeRef) -> bytes:
        """Read back the blob a reference points at.

        :param ref: reference to the blob to read.
        :type ref: JobLargeRef
        :return: the stored bytes.
        :rtype: bytes
        :raises FileNotFoundError: the blob has expired or is missing.
        """

    @abstractmethod
    def delete(self, ref: JobLargeRef) -> None:
        """Remove the blob a reference points at. Idempotent (no-op if gone).

        :param ref: reference to the blob to remove.
        :type ref: JobLargeRef
        """
