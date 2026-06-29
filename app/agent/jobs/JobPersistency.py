"""Redis CRUD for JobState plus the per-user / pending / schedule indexes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.AgentConst import (
    JOB_STATE_INDEX_PENDING, JOB_STATE_INDEX_SCHEDULE, JOB_STATE_INDEX_USER, JOB_STATE_KEY_PREFIX,
)
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis


class JobPersistency:
    """JobState storage backed by Redis with secondary indexes for listing.

    Independent from Celery's result backend so we can carry ``user_uid``,
    ``payload``, ``attempts``, ``schedule_name`` and a configurable TTL - none
    of which fit in Celery's ``AsyncResult``. Three sorted-set indexes are kept
    in sync with the documents: one per user, one for pending jobs, one per
    periodic schedule.
    """

    def __init__(self, client: ClientRedis, ttl_seconds: int) -> None:
        self._client: ClientRedis = client
        self._ttl_seconds: int = ttl_seconds

    def save(self, state: JobState) -> None:
        """Write the document and keep the per-user / pending / schedule indexes in sync.

        :param state: the JobState to persist. The status drives the pending
            index: terminal statuses are removed from it, non-terminal ones are
            added or updated.
        :type state: JobState
        """
        self._client.set(self._key(state.job_id), state.to_dict(), ttl=self._ttl_seconds)
        score: float = state.date_planned.timestamp()
        if state.user_uid:
            self._client.zset_add(self._index_user_key(state.user_uid), state.job_id, score)
        if JobStatus.is_terminal(state.status):
            self._client.zset_remove(JOB_STATE_INDEX_PENDING, state.job_id)
        else:
            self._client.zset_add(JOB_STATE_INDEX_PENDING, state.job_id, score)
        if state.schedule_name:
            self._client.zset_add(self._index_schedule_key(state.schedule_name), state.job_id, score)

    def get(self, job_id: str) -> JobState | None:
        """Return the JobState for ``job_id``, or ``None`` if expired or unknown.

        :param job_id: id of the job to look up.
        :type job_id: str
        :return: the deserialised JobState, or ``None`` when the Redis key
            is missing.
        :rtype: JobState | None
        """
        data: str | list | dict | None = self._client.get(self._key(job_id), dict)
        return JobState.from_dict(data) if isinstance(data, dict) else None

    def list_by_user(self, user_uid: str, *, limit: int = 100) -> list[JobState]:
        """Return the user's jobs, newest planned first.

        :param user_uid: identifier of the user whose jobs are returned.
        :type user_uid: str
        :param limit: maximum number of jobs to return.
        :type limit: int
        :return: JobStates sorted by ``date_planned`` descending.
        :rtype: list[JobState]
        """
        index_key: str = self._index_user_key(user_uid)
        return self._fetch_many(index_key, self._client.zset_revrange(index_key, 0, limit - 1))

    def list_pending(self, *, limit: int = 500) -> list[JobState]:
        """Return non-terminal JobStates across all users, newest planned first.

        :param limit: maximum number of jobs to return.
        :type limit: int
        :return: JobStates whose status is not in ``{SUCCESS, FAILURE, CANCELED}``.
        :rtype: list[JobState]
        """
        return self._fetch_many(
            JOB_STATE_INDEX_PENDING, self._client.zset_revrange(JOB_STATE_INDEX_PENDING, 0, limit - 1),
        )

    def list_by_schedule(self, schedule_name: str, *, limit: int = 100) -> list[JobState]:
        """Return JobStates tagged with a periodic schedule name, newest first.

        :param schedule_name: identifier of the periodic schedule to inspect.
        :type schedule_name: str
        :param limit: maximum number of firings to return.
        :type limit: int
        :return: JobStates produced by this schedule, sorted by ``date_planned``
            descending.
        :rtype: list[JobState]
        """
        index_key: str = self._index_schedule_key(schedule_name)
        return self._fetch_many(index_key, self._client.zset_revrange(index_key, 0, limit - 1))

    def delete(self, job_id: str) -> None:
        """Drop a JobState document and every index entry pointing at it.

        :param job_id: id of the job to remove. No-op when the document has
            already expired.
        :type job_id: str
        """
        state: JobState | None = self.get(job_id)
        self._client.delete(self._key(job_id))
        self._client.zset_remove(JOB_STATE_INDEX_PENDING, job_id)
        if state is not None:
            if state.user_uid:
                self._client.zset_remove(self._index_user_key(state.user_uid), job_id)
            if state.schedule_name:
                self._client.zset_remove(self._index_schedule_key(state.schedule_name), job_id)

    def _fetch_many(self, index_key: str, job_ids: list[str]) -> list[JobState]:
        """Resolve job ids into JobStates, pruning index entries whose doc expired.

        Indexes can lag behind TTL expiry: an id may still appear in a sorted
        set after its document has been evicted. Such dangling ids are removed
        from ``index_key`` on the fly so the sorted set does not grow unbounded.

        :param index_key: the sorted set the ids came from, pruned of dead entries.
        :type index_key: str
        :param job_ids: ids read from that index, newest first.
        :type job_ids: list[str]
        :return: the JobStates still present, in input order.
        :rtype: list[JobState]
        """
        result: list[JobState] = []
        stale: list[str] = []
        for job_id in job_ids:
            state: JobState | None = self.get(job_id)
            if state is not None:
                result.append(state)
            else:
                stale.append(job_id)
        if stale:
            self._client.zset_remove(index_key, *stale)
        return result

    @staticmethod
    def _key(job_id: str) -> str:
        return f"{JOB_STATE_KEY_PREFIX}{job_id}"

    @staticmethod
    def _index_user_key(user_uid: str) -> str:
        return f"{JOB_STATE_INDEX_USER}{user_uid}"

    @staticmethod
    def _index_schedule_key(schedule_name: str) -> str:
        return f"{JOB_STATE_INDEX_SCHEDULE}{schedule_name}"
