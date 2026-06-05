from __future__ import annotations

from enum import Enum


class JobStatus(Enum):
    """Lifecycle status of an Agent job, mirrored from Celery signals into the JobState store."""

    PENDING = "pending"      # accepted by the broker, not yet picked up by a worker
    STARTED = "started"      # picked up, currently executing
    SUCCESS = "success"      # finished normally
    FAILURE = "failure"      # raised an exception
    RETRY = "retry"          # transient failure, will be re-executed
    CANCELED = "canceled"    # explicitly revoked or interrupted via SIGTERM/SIGKILL

    @classmethod
    def is_terminal(cls, status: "JobStatus") -> bool:
        """Return True for statuses that mark the end of a job's life."""
        return status in {cls.SUCCESS, cls.FAILURE, cls.CANCELED}
