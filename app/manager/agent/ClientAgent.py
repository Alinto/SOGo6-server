"""Single entry point Flask uses to talk to the Agent."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus
from app.agent.jobs.job_large_store.JobLargeStorage import JobLargeStorage
from app.agent.jobs.job_large_store.JobLargeStore import JobLargeStore
from app.agent.jobs.job_large_store.JobLargeStoreFile import JobLargeStoreFile
from app.agent.jobs.job_large_store.JobLargeStoreInMemory import JobLargeStoreInMemory
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_agent
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.jobs.Job import Job
    from app.agent.jobs.JobCanceller import JobCanceller
    from app.agent.jobs.JobPersistency import JobPersistency
    from app.agent.jobs.JobRequest import JobRequest
    from app.manager.cache.ClientRedis import ClientRedis


class ClientAgent:
    """Facade composing Agent, JobPersistency and JobCanceller behind a single API."""

    def __init__(
        self, agent: Agent, persistency: JobPersistency, canceller: JobCanceller,
        cache: ClientRedis, large_storage: JobLargeStorage,
    ) -> None:
        self._agent: Agent = agent
        self._persistency: JobPersistency = persistency
        self._canceller: JobCanceller = canceller
        self._cache: ClientRedis = cache
        # The backend kind is resolved from config at wiring time and injected, like the
        # Redis URL into ClientRedis. ClientAgent builds the instance because it holds the
        # cache the in-memory backend needs injected.
        self.large_store: JobLargeStore = self._build_large_store(large_storage, cache)

    @staticmethod
    def _build_large_store(storage: JobLargeStorage, cache: ClientRedis) -> JobLargeStore:
        """Build the large-blob backend for the requested storage kind."""
        if storage == JobLargeStorage.FILE:
            return JobLargeStoreFile()
        return JobLargeStoreInMemory(cache)

    def enqueue(
        self, request: JobRequest, *,
        user_uid: str | None = None, eta: datetime | None = None,
    ) -> str:
        """Schedule a job and persist its PENDING state before publishing.

        The job id is generated locally so the state hits Redis before the
        message hits the broker - otherwise a fast worker could run
        ``task_prerun`` while the state is still missing.

        Enforces ``request.max_concurrent`` by acquiring a Redis SET NX lock
        keyed by ``(name, user_uid)`` before persisting the state. The lock
        is released by the terminal lifecycle hooks (success / failure /
        revoked) and auto-expires after ``soft_timeout_seconds + 60`` as a
        safety net for crashed workers. ``max_concurrent == 0`` skips the gate.

        :param request: typed Request carrying the job name and payload.
        :type request: JobRequest
        :param user_uid: owner of the job; ``None`` for system jobs.
        :type user_uid: str | None
        :param eta: earliest time the worker may pick the job up. ``None``
            means as soon as possible.
        :type eta: datetime | None
        :return: id of the scheduled job.
        :rtype: str
        :raises RequestException: ERROR_JOB_CONCURRENT_LIMIT when another job
            of the same name is still in flight for the same scope.
        """
        job_name: str = request.name
        payload: dict = request.payload()
        job_id: str = generate_uuid()
        self._acquire_concurrency_lock(request, user_uid)
        try:
            state: JobState = JobState(
                job_id=job_id, name=job_name, status=JobStatus.PENDING,
                user_uid=user_uid, date_planned=datetime.now(timezone.utc),
                payload=payload,
                max_try=request.max_try,
                soft_timeout_seconds=request.soft_timeout_seconds,
                max_concurrent=request.max_concurrent,
            )
            self._persistency.save(state)
            self._agent.create_job(job_name, payload, user_uid=user_uid, eta=eta, job_id=job_id)
        except Exception:
            # Release the lock if anything between acquisition and broker publish failed,
            # otherwise the scope stays blocked until the TTL expires with no in-flight job.
            if request.max_concurrent > 0:
                self._cache.delete(JobState.concurrency_lock_key(job_name, user_uid))
            raise
        logger_agent.info(
            "ClientAgent.enqueue: name=%s job_id=%s user_uid=%s eta=%s",
            job_name, job_id, user_uid, eta,
        )
        return job_id

    def _acquire_concurrency_lock(self, request: JobRequest, user_uid: str | None) -> None:
        """Acquire the per-scope concurrency lock; raise CONCURRENT_LIMIT if held.

        N=1 only: uses ``SET NX EX``. ``max_concurrent == 0`` disables the gate.
        N>1 will require a counter / sorted-set and is not implemented yet.
        """
        if request.max_concurrent <= 0:
            return
        if request.max_concurrent > 1:
            raise NotImplementedError("max_concurrent > 1 not supported yet")
        lock_key: str = JobState.concurrency_lock_key(request.name, user_uid)
        lock_ttl: int = request.soft_timeout_seconds + 60
        if not self._cache.set(lock_key, "1", ttl=lock_ttl, nx=True):
            raise RequestException(error=err.ERROR_JOB_CONCURRENT_LIMIT)

    def start(self, request: JobRequest, *, user_uid: str | None = None) -> str:
        """Run a job immediately.

        Equivalent to :meth:`enqueue` with ``eta=datetime.now()``.

        :param request: typed Request carrying the job name and payload.
        :type request: JobRequest
        :param user_uid: owner of the job; ``None`` for system jobs.
        :type user_uid: str | None
        :return: id of the scheduled job.
        :rtype: str
        """
        return self.enqueue(request, user_uid=user_uid, eta=datetime.now(timezone.utc))

    def get(self, job_id: str) -> JobState | None:
        """Return the JobState for ``job_id``, flipping zombie STARTED records to FAILURE.

        A STARTED state that has been running far beyond its declared soft
        timeout is rewritten to FAILURE on the fly: the caller never sees a
        record stuck in STARTED forever, even if the worker died before the
        lifecycle hooks could fire.

        :param job_id: id of the job to look up.
        :type job_id: str
        :return: the JobState, or ``None`` when the document has expired or
            never existed.
        :rtype: JobState | None
        """
        state: JobState | None = self._persistency.get(job_id)
        if state is not None and state.status == JobStatus.STARTED and self._is_zombie(state):
            state.status = JobStatus.FAILURE
            state.error = "Job interrupted: worker disappeared without finishing"
            state.date_end = datetime.now(timezone.utc)
            if state.date_start:
                state.duration_seconds = (state.date_end - state.date_start).total_seconds()
            self._persistency.save(state)
            logger_agent.warning(
                "ClientAgent.get: zombie job job_id=%s name=%s marked FAILURE",
                job_id, state.name,
            )
        return state

    def cancel(self, job_id: str) -> None:
        """SIGTERM -> grace wait -> SIGKILL via JobCanceller. Idempotent."""
        logger_agent.info("ClientAgent.cancel: job_id=%s", job_id)
        self._canceller.cancel(job_id)

    def get_job_handler(self, name: str) -> Job | None:
        """Return the registered job handler for ``name``, used to shape the public view."""
        return self._agent.get_job_handler(name)

    def list_by_user(self, user_uid: str, *, limit: int = 100) -> list[JobState]:
        """Newest planned first, scoped to a user."""
        return self._persistency.list_by_user(user_uid, limit=limit)

    def list_pending(self, *, limit: int = 500) -> list[JobState]:
        """Non-terminal JobStates, newest planned first."""
        return self._persistency.list_pending(limit=limit)

    def list_by_schedule(self, schedule_name: str, *, limit: int = 100) -> list[JobState]:
        """JobStates tagged with a periodic schedule, newest first."""
        return self._persistency.list_by_schedule(schedule_name, limit=limit)

    def _is_zombie(self, state: JobState) -> bool:
        # Heuristic: 2x soft timeout leaves room for the real worker to raise
        # SoftTimeLimitExceeded and update the state itself before we declare it lost.
        if state.date_start is None or state.soft_timeout_seconds <= 0:
            return False
        running_for: float = (datetime.now(timezone.utc) - state.date_start).total_seconds()
        return running_for > (2 * state.soft_timeout_seconds)
