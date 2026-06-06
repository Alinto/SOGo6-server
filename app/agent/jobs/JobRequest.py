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

    @abstractmethod
    def payload(self) -> dict[str, Any]:
        """Serialise the typed fields into the dict handed to the worker."""
