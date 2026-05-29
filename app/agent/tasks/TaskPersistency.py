"""Redis CRUD for TaskState plus the per-user / pending / schedule indexes."""
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
    """TaskState storage backed by Redis with secondary indexes for listing.

    Independent from Celery's result backend so we can carry user_uid, payload, attempts,
    schedule_name and a configurable TTL — none of which fit in ``AsyncResult``.
    """

    def __init__(self, client: ClientRedis, ttl_seconds: int) -> None:
        self._client: ClientRedis = client
        self._ttl_seconds: int = ttl_seconds

    def save(self, state: TaskState) -> None:
        """Write the document and keep the user/pending/schedule indexes in sync."""
        self._client.set(self._key(state.task_id), state.to_dict(), ttl=self._ttl_seconds)
        score: float = state.date_planned.timestamp()
        if state.user_uid:
            self._client.zset_add(self._index_user_key(state.user_uid), state.task_id, score)
        if TaskStatus.is_terminal(state.status):
            self._client.zset_remove(TASK_STATE_INDEX_PENDING, state.task_id)
        else:
            self._client.zset_add(TASK_STATE_INDEX_PENDING, state.task_id, score)
        if state.schedule_name:
            self._client.zset_add(self._index_schedule_key(state.schedule_name), state.task_id, score)

    def get(self, task_id: str) -> TaskState | None:
        """Return the TaskState, or None if expired/unknown."""
        data = self._client.get(self._key(task_id), dict)
        return TaskState.from_dict(data) if isinstance(data, dict) else None

    def list_by_user(self, user_uid: str, *, limit: int = 100) -> list[TaskState]:
        """Newest planned first, scoped to a user."""
        return self._fetch_many(self._zset_revrange(self._index_user_key(user_uid), 0, limit - 1))

    def list_pending(self, *, limit: int = 500) -> list[TaskState]:
        """Non-terminal TaskStates, newest planned first."""
        return self._fetch_many(self._zset_revrange(TASK_STATE_INDEX_PENDING, 0, limit - 1))

    def list_by_schedule(self, schedule_name: str, *, limit: int = 100) -> list[TaskState]:
        """Firings of a Beat schedule, newest first."""
        return self._fetch_many(self._zset_revrange(self._index_schedule_key(schedule_name), 0, limit - 1))

    def delete(self, task_id: str) -> None:
        """Drop a TaskState and all of its index entries."""
        state: TaskState | None = self.get(task_id)
        self._client.delete(self._key(task_id))
        self._client.zset_remove(TASK_STATE_INDEX_PENDING, task_id)
        if state is not None:
            if state.user_uid:
                self._client.zset_remove(self._index_user_key(state.user_uid), task_id)
            if state.schedule_name:
                self._client.zset_remove(self._index_schedule_key(state.schedule_name), task_id)

    def _fetch_many(self, task_ids: list[str]) -> list[TaskState]:
        # Indexes can lag behind TTL expiry; silently skip missing entries.
        result: list[TaskState] = []
        for task_id in task_ids:
            state = self.get(task_id)
            if state is not None:
                result.append(state)
        return result

    def _zset_revrange(self, key: str, start: int, stop: int) -> list[str]:
        # ClientRedis doesn't expose zrevrange yet; reach through to the underlying client.
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
