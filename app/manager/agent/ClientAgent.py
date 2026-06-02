"""Single entry point Flask uses to talk to the Agent."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.agent.tasks.TaskState import TaskState
from app.agent.tasks.TaskStatus import TaskStatus
from app.utils.logger.logger import logger_agent
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.agent.Agent import Agent
    from app.agent.tasks.TaskCanceller import TaskCanceller
    from app.agent.tasks.TaskPersistency import TaskPersistency
    from app.agent.tasks.TaskRequest import TaskRequest


class ClientAgent:
    """Façade composing Agent, TaskPersistency and TaskCanceller behind a single API."""

    def __init__(
        self, agent: Agent, persistency: TaskPersistency, canceller: TaskCanceller,
    ) -> None:
        self._agent: Agent = agent
        self._persistency: TaskPersistency = persistency
        self._canceller: TaskCanceller = canceller

    def enqueue(
        self, request: TaskRequest, *,
        user_uid: str | None = None, eta: datetime | None = None,
    ) -> str:
        """Schedule a task and persist its PENDING state before publishing.

        The task id is generated locally so the state hits Redis before the
        message hits the broker — otherwise a fast worker could run
        ``task_prerun`` while the state is still missing.

        :param request: typed Request carrying the task name and payload.
        :type request: TaskRequest
        :param user_uid: owner of the task; ``None`` for system tasks.
        :type user_uid: str | None
        :param eta: earliest time the worker may pick the task up. ``None``
            means as soon as possible.
        :type eta: datetime | None
        :return: id of the scheduled task.
        :rtype: str
        """
        task_name: str = request.name
        payload: dict = request.payload()
        task_id: str = generate_uuid()
        state: TaskState = TaskState(
            task_id=task_id, name=task_name, status=TaskStatus.PENDING,
            user_uid=user_uid, date_planned=datetime.now(timezone.utc),
            payload=payload,
            max_try=request.max_try,
            soft_timeout_seconds=request.soft_timeout_seconds,
        )
        self._persistency.save(state)
        self._agent.create_task(task_name, payload, user_uid=user_uid, eta=eta, task_id=task_id)
        logger_agent.info(
            "ClientAgent.enqueue: name=%s task_id=%s user_uid=%s eta=%s",
            task_name, task_id, user_uid, eta,
        )
        return task_id

    def start(self, request: TaskRequest, *, user_uid: str | None = None) -> str:
        """Run a task immediately.

        Equivalent to :meth:`enqueue` with ``eta=datetime.now()``.

        :param request: typed Request carrying the task name and payload.
        :type request: TaskRequest
        :param user_uid: owner of the task; ``None`` for system tasks.
        :type user_uid: str | None
        :return: id of the scheduled task.
        :rtype: str
        """
        return self.enqueue(request, user_uid=user_uid, eta=datetime.now(timezone.utc))

    def get(self, task_id: str) -> TaskState | None:
        """Return the TaskState for ``task_id``, flipping zombie STARTED records to FAILURE.

        A STARTED state that has been running far beyond its declared soft
        timeout is rewritten to FAILURE on the fly: the caller never sees a
        record stuck in STARTED forever, even if the worker died before the
        lifecycle hooks could fire.

        :param task_id: id of the task to look up.
        :type task_id: str
        :return: the TaskState, or ``None`` when the document has expired or
            never existed.
        :rtype: TaskState | None
        """
        state = self._persistency.get(task_id)
        if state is not None and state.status == TaskStatus.STARTED and self._is_zombie(state):
            state.status = TaskStatus.FAILURE
            state.error = "Task interrupted: worker disappeared without finishing"
            state.date_end = datetime.now(timezone.utc)
            if state.date_start:
                state.duration_seconds = (state.date_end - state.date_start).total_seconds()
            self._persistency.save(state)
            logger_agent.warning(
                "ClientAgent.get: zombie task task_id=%s name=%s marked FAILURE",
                task_id, state.name,
            )
        return state

    def cancel(self, task_id: str) -> None:
        """SIGTERM → grace wait → SIGKILL via TaskCanceller. Idempotent."""
        logger_agent.info("ClientAgent.cancel: task_id=%s", task_id)
        self._canceller.cancel(task_id)

    def list_by_user(self, user_uid: str, *, limit: int = 100) -> list[TaskState]:
        """Newest planned first, scoped to a user."""
        return self._persistency.list_by_user(user_uid, limit=limit)

    def list_pending(self, *, limit: int = 500) -> list[TaskState]:
        """Non-terminal TaskStates, newest planned first."""
        return self._persistency.list_pending(limit=limit)

    def list_by_schedule(self, schedule_name: str, *, limit: int = 100) -> list[TaskState]:
        """Firings of a Beat schedule, newest first."""
        return self._persistency.list_by_schedule(schedule_name, limit=limit)

    def _is_zombie(self, state: TaskState) -> bool:
        # Heuristic: 2x soft timeout leaves room for the real worker to raise
        # SoftTimeLimitExceeded and update the state itself before we declare it lost.
        if state.date_start is None or state.soft_timeout_seconds <= 0:
            return False
        running_for: float = (datetime.now(timezone.utc) - state.date_start).total_seconds()
        return running_for > (2 * state.soft_timeout_seconds)
