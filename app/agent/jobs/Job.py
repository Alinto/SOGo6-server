from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.jobs.JobRequest import JobRequest


# Collection of Job classes populated at import-time by ``@agent_job``.
# Read once at boot by ``Agent.register_all_job_handlers``.
_AGENT_JOB_CLASSES: list[type[Job]] = []


def agent_job(cls: type[Job]) -> type[Job]:
    """Class decorator: queue ``cls`` for later registration by ``Agent.register_all_job_handlers``.

    Decoration is a pure module-level side-effect: no agent instance is touched
    here, so ``Job`` stays free of any dependency on the singleton. The
    actual Celery wiring happens later when the agent iterates the collection
    and calls ``register_job_handler`` for each entry.

    :param cls: a ``Job`` subclass to enrol.
    :type cls: type[Job]
    :return: the class itself, unchanged.
    :rtype: type[Job]
    """
    _AGENT_JOB_CLASSES.append(cls)
    return cls


def collected_agent_class_jobs() -> list[type[Job]]:
    """Snapshot of every class decorated with :func:`agent_job`.

    Returns a shallow copy so callers cannot accidentally mutate the registry.
    """
    return list(_AGENT_JOB_CLASSES)


class AgentJobCancelled(InterruptedError):
    """Raised inside a Job to signal cooperative cancellation.

    Long-running jobs should catch this to clean up before exiting, then let
    it propagate so Celery's ``task_revoked`` signal fires and the JobState
    is marked CANCELED.
    """


class Job(ABC):
    """Base class for every Agent job.

    Subclasses set ``request_class`` to their companion ``JobRequest`` and
    implement :meth:`process`. The Request is the single source of truth for the
    job name and execution metadata (``max_try``, ``soft_timeout_seconds``,
    ``resume``) - the Job reads everything through it.

    Jobs run under at-least-once delivery: a worker crash mid-run or a retry can
    execute the same job more than once, so :meth:`process` must be idempotent -
    re-running it must not double any side effect (no duplicate row, no double
    send). Make the side effect keyed/upsert-based rather than blind-append.
    """

    request_class: ClassVar[type[JobRequest]]

    # Writes the completion percentage of a running job; bound by ``Agent.register_job_handler``.
    _progress_writer: Callable[[str, int], None] | None = None

    def bind_progress_writer(self, writer: Callable[[str, int], None]) -> None:
        """Attach the callable persisting the progress of a job (``writer(job_id, percent)``).

        :param writer: callable storing the percentage in the job's ``JobState``.
        :type writer: Callable[[str, int], None]
        """
        self._progress_writer = writer

    def report_progress(self, job_id: str, done: int, total: int) -> None:
        """Publish the completion of the running job, exposed as ``progress`` by ``GET /jobs/<id>``.

        Jobs that can measure their work call it as it advances (e.g. after each batch).
        No-op when no writer is bound (job run outside the worker, e.g. in tests).

        :param job_id: id of the running job, as received by :meth:`process`.
        :type job_id: str
        :param done: number of work units already processed.
        :type done: int
        :param total: total number of work units; ``0`` means nothing to do (100%).
        :type total: int
        """
        if self._progress_writer is None:
            return
        percent: int = 100 if total <= 0 else min(100, done * 100 // total)
        self._progress_writer(job_id, percent)

    @abstractmethod
    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Execute the job's business logic and return a JSON-serialisable result.

        Subclasses must override this. The returned dict is stored under
        ``JobState.result`` after Celery's ``task_postrun`` signal fires -
        keep it small. For sizeable outputs (ICS exports, blobs), persist them
        via the agent blob store and return only the reference here.

        :param payload: dict produced by ``JobRequest.payload`` on the caller side.
            Concrete jobs usually rehydrate the matching Request via
            ``<Request>(**payload)``.
        :type payload: dict[str, Any]
        :param user_uid: identifier of the user owning the job. ``None`` for
            system jobs (purges, maintenance). Jobs that act on user-scoped
            data should reject ``None`` explicitly.
        :type user_uid: str | None
        :param job_id: id assigned by Celery for this invocation. Passed
            through for tracing or correlation; not required by every job.
        :type job_id: str
        :return: JSON-serialisable result dict, written to ``JobState.result``.
        :rtype: dict[str, Any]
        """

    def public_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the payload as exposed to the owner through the read API.

        The default echoes the payload unchanged. Override it when the job
        receives sensitive inputs (tokens, passwords, internal references) that
        must not be reflected back through ``GET /jobs/<id>``: return a copy with
        those fields removed or masked.

        Rule of thumb: never put a secret in a payload without redacting it here.
        The payload still reaches the worker in full - only the API view is shaped.

        :param payload: the raw payload stored in ``JobState.payload``.
        :type payload: dict[str, Any]
        :return: the payload safe to expose to the job owner.
        :rtype: dict[str, Any]
        """
        return payload

    def _run(self, job_id: str, payload: dict[str, Any], user_uid: str | None) -> dict[str, Any]:
        """Entry point called by the Celery wrapper installed in ``Agent.register_job_handler``.

        Bridges the Celery-side positional signature ``(job_id, payload, user_uid)``
        to the keyword-friendly :meth:`process`. Private by convention - subclasses
        override :meth:`process`, not this one.

        :param job_id: id assigned by Celery, taken from ``self.request.id`` in
            the wrapper.
        :type job_id: str
        :param payload: dict received from the broker.
        :type payload: dict[str, Any]
        :param user_uid: owner of the job or ``None`` for system jobs.
        :type user_uid: str | None
        :return: whatever :meth:`process` returns.
        :rtype: dict[str, Any]
        """
        return self.process(payload, user_uid=user_uid, job_id=job_id)
