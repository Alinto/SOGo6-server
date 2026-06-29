"""Contract callers use to publish a job.

Each concrete job ships with its own Request: a typed dataclass that declares
the target job name, the execution metadata (max_try, soft_timeout_seconds,
resume) and exposes a ``payload`` method building the dict sent to the worker.
Callers (Flask interfaces, tests) only import the Request - never the
``Job`` subclass - keeping the implementation private to the worker side.

The Request is the **source of truth** for the metadata: the matching ``Job``
mirrors them so Celery's decorator and the lifecycle hooks see the same values.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class JobRequest(ABC):
    """Typed request published through ``ClientAgent.enqueue`` / ``start``.

    Subclasses set ``name`` to the registered job name, optionally override the
    execution metadata, and implement ``payload`` to return a JSON-serialisable
    dict matching what ``Job.process`` expects.
    """

    name: ClassVar[str]
    max_try: ClassVar[int] = 1
    soft_timeout_seconds: ClassVar[int] = 300
    resume: ClassVar[bool] = True
    # Number of jobs of this type allowed in flight (non-terminal) at the same time
    # per scope. This caps simultaneity, not total throughput: once a job finishes,
    # the slot frees up - it is NOT an anti-duplicate guard. 0 disables the gate.
    max_concurrent: ClassVar[int] = 1
    # Standard 5-field cron expression ("minute hour day-of-month month day-of-week").
    # Set it to make the job fire periodically through Celery Beat; left None, the job
    # runs only on demand. A periodic Request must be constructible with no arguments
    # (Beat supplies no caller input).
    cron: ClassVar[str | None] = None
    # Which exceptions are retried (max_try = how many times, retry_for = for which errors).
    # Default retries on anything; narrow it to errors a retry can fix so the job fails fast
    # on permanent ones instead of burning attempts. E.g. with max_try = 5 and
    # retry_for = (ConnectionError,): an unreachable host is retried, a malformed payload
    # fails at once.
    retry_for: ClassVar[tuple[type[Exception], ...]] = (Exception,)

    @abstractmethod
    def payload(self) -> dict[str, Any]:
        """Serialise the typed fields into the dict handed to the worker."""
