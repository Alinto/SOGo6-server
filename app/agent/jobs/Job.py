from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, TYPE_CHECKING

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
    """

    request_class: ClassVar[type[JobRequest]]

    @abstractmethod
    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Execute the job's business logic and return a JSON-serialisable result.

        Subclasses must override this. The returned dict is stored under
        ``JobState.result`` after Celery's ``task_postrun`` signal fires -
        keep it small. For sizeable outputs (ICS exports, blobs), persist them
        via ``JobLargeStore`` and return only the reference here.

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
