"""Redis persistence layer for :class:`TaskState`.

This is **not** the Celery result backend. ``AsyncResult.get()`` only knows
``status / result / traceback``; it carries no ``user_uid``, ``domain``, ``payload``,
nor any per-user index. Going through Redis directly gives us a richer, indexable
applicative view of every task — and keeps the admin API independent of Celery, so a
future swap of task framework only touches the Agent layer.

The data layout is intentionally small and built around Redis primitives:

- ``taskstate:<id>`` — JSON document holding the full :class:`TaskState`.
- ``taskstate:index:user:<user_uid>`` — sorted set, members are task ids and scores are the
  ``date_planned`` epoch. Used by the admin API to list a user's tasks newest-first.
- ``taskstate:index:pending`` — sorted set of tasks that haven't reached a terminal status.
  Used by the cancellation flow and the periodic purge.

Listing avoids ``KEYS *`` entirely: everything goes through the sorted-set indexes, which
remain O(log N) per operation. Terminal entries are removed from the pending index on save.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.AgentConst import (
    TASK_STATE_INDEX_PENDING, TASK_STATE_INDEX_SCHEDULE, TASK_STATE_INDEX_USER, TASK_STATE_KEY_PREFIX,
)
from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis


class TaskPersistency:
    """CRUD and listing for TaskState records held in Redis."""

    def __init__(self, client: ClientRedis, ttl_seconds: int) -> None:
        self._client: ClientRedis = client
        self._ttl_seconds: int = ttl_seconds

    def save(self, state: TaskState) -> None:
        """Write the TaskState document and keep the user/pending/schedule indexes in sync."""
        key: str = self._key(state.task_id)
        self._client.set(key, state.to_dict(), ttl=self._ttl_seconds)

        # Track the task in the per-user index sorted by planned time.
        score: float = state.date_planned.timestamp()
        self._client.zset_add(self._index_user_key(state.user_uid), state.task_id, score)

        # Pending index: keep the task while it's alive, drop it the moment it reaches
        # a terminal status so cancellation/purge don't scan dead entries.
        if TaskStatus.is_terminal(state.status):
            self._client.zset_remove(TASK_STATE_INDEX_PENDING, state.task_id)
        else:
            self._client.zset_add(TASK_STATE_INDEX_PENDING, state.task_id, score)

        # Schedule index: every firing of a Celery Beat task lands in the same zset so the
        # admin API can list the history of a recurring schedule.
        if state.schedule_name:
            self._client.zset_add(self._index_schedule_key(state.schedule_name), state.task_id, score)

    def get(self, task_id: str) -> TaskState | None:
        """Return the TaskState for this id, or None if expired/unknown."""
        data = self._client.get(self._key(task_id), dict)
        return TaskState.from_dict(data) if isinstance(data, dict) else None

    def list_by_user(self, user_uid: str, *, limit: int = 100) -> list[TaskState]:
        """Return the user's tasks, newest planned first."""
        task_ids: list[str] = self._zset_revrange(self._index_user_key(user_uid), 0, limit - 1)
        return self._fetch_many(task_ids)

    def list_pending(self, *, limit: int = 500) -> list[TaskState]:
        """Return all non-terminal tasks, newest planned first (used by cancel/purge flows)."""
        task_ids: list[str] = self._zset_revrange(TASK_STATE_INDEX_PENDING, 0, limit - 1)
        return self._fetch_many(task_ids)

    def list_by_schedule(self, schedule_name: str, *, limit: int = 100) -> list[TaskState]:
        """Return every firing of a Celery Beat schedule, newest first."""
        task_ids: list[str] = self._zset_revrange(self._index_schedule_key(schedule_name), 0, limit - 1)
        return self._fetch_many(task_ids)

    def delete(self, task_id: str) -> None:
        """Drop a TaskState and clean up every index entry referencing it."""
        state: TaskState | None = self.get(task_id)
        self._client.delete(self._key(task_id))
        self._client.zset_remove(TASK_STATE_INDEX_PENDING, task_id)
        if state is not None:
            self._client.zset_remove(self._index_user_key(state.user_uid), task_id)
            if state.schedule_name:
                self._client.zset_remove(self._index_schedule_key(state.schedule_name), task_id)

    def _fetch_many(self, task_ids: list[str]) -> list[TaskState]:
        """Resolve a list of ids to TaskState objects, skipping any that have expired."""
        result: list[TaskState] = []
        for task_id in task_ids:
            state = self.get(task_id)
            if state is not None:
                result.append(state)
        return result

    def _zset_revrange(self, key: str, start: int, stop: int) -> list[str]:
        """Return zset members highest-score-first.

        ``ClientRedis`` does not expose plain ``zrevrange``; we reach through to the
        underlying redis-py client. Wrapped here so the rest of the persistency layer stays
        backend-agnostic if we extend ``ClientRedis`` later.
        """
        raw: list = self._client.redis.zrevrange(key, start, stop)  # type: ignore[assignment]
        return [m.decode("utf-8") if isinstance(m, bytes) else str(m) for m in raw]

    @staticmethod
    def _key(task_id: str) -> str:
        return f"{TASK_STATE_KEY_PREFIX}{task_id}"

    @staticmethod
    def _index_user_key(user_uid: str) -> str:
        return f"{TASK_STATE_INDEX_USER}{user_uid}"

    @staticmethod
    def _index_schedule_key(schedule_name: str) -> str:
        return f"{TASK_STATE_INDEX_SCHEDULE}{schedule_name}"
