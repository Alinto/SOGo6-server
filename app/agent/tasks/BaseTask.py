from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.tasks.TaskRequest import TaskRequest


# Collection of Task classes populated at import-time by ``@agent_task``.
# Read once at boot by ``Agent.register_all_task_handlers``.
_AGENT_TASK_CLASSES: list[type[BaseTask]] = []


def agent_task(cls: type[BaseTask]) -> type[BaseTask]:
    """Class decorator: queue ``cls`` for later registration by ``Agent.register_all_task_handlers``.

    Decoration is a pure module-level side-effect: no agent instance is touched
    here, so ``BaseTask`` stays free of any dependency on the singleton. The
    actual Celery wiring happens later when the agent iterates the collection
    and calls ``register_task_handler`` for each entry.

    :param cls: a ``BaseTask`` subclass to enrol.
    :type cls: type[BaseTask]
    :return: the class itself, unchanged.
    :rtype: type[BaseTask]
    """
    _AGENT_TASK_CLASSES.append(cls)
    return cls


def collected_agent_class_tasks() -> list[type[BaseTask]]:
    """Snapshot of every class decorated with :func:`agent_task`.

    Returns a shallow copy so callers cannot accidentally mutate the registry.
    """
    return list(_AGENT_TASK_CLASSES)


class AgentTaskCancelled(InterruptedError):
    """Raised inside a Task to signal cooperative cancellation.

    Long-running tasks should catch this to clean up before exiting, then let
    it propagate so Celery's ``task_revoked`` signal fires and the TaskState
    is marked CANCELED.
    """


class BaseTask(ABC):
    """Base class for every Agent task.

    Subclasses set ``request_class`` to their companion ``TaskRequest`` and
    implement :meth:`process`. The Request is the single source of truth for the
    task name and execution metadata (``max_try``, ``soft_timeout_seconds``,
    ``resume``) — the Task reads everything through it.
    """

    request_class: ClassVar[type[TaskRequest]]

    @abstractmethod
    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, task_id: str,
    ) -> dict[str, Any]:
        """Execute the task's business logic and return a JSON-serialisable result.

        Subclasses must override this. The returned dict is stored under
        ``TaskState.result`` after Celery's ``task_postrun`` signal fires —
        keep it small. For sizeable outputs (ICS exports, blobs), persist them
        via ``TaskResultLargeStore`` and return only the reference here.

        :param payload: dict produced by ``TaskRequest.payload`` on the caller side.
            Concrete tasks usually rehydrate the matching Request via
            ``<Request>(**payload)``.
        :type payload: dict[str, Any]
        :param user_uid: identifier of the user owning the task. ``None`` for
            system tasks (purges, maintenance). Tasks that act on user-scoped
            data should reject ``None`` explicitly.
        :type user_uid: str | None
        :param task_id: id assigned by Celery for this invocation. Passed
            through for tracing or correlation; not required by every task.
        :type task_id: str
        :return: JSON-serialisable result dict, written to ``TaskState.result``.
        :rtype: dict[str, Any]
        """

    def _run(self, task_id: str, payload: dict[str, Any], user_uid: str | None) -> dict[str, Any]:
        """Entry point called by the Celery wrapper installed in ``Agent.register_task_handler``.

        Bridges the Celery-side positional signature ``(task_id, payload, user_uid)``
        to the keyword-friendly :meth:`process`. Private by convention — subclasses
        override :meth:`process`, not this one.

        :param task_id: id assigned by Celery, taken from ``self.request.id`` in
            the wrapper.
        :type task_id: str
        :param payload: dict received from the broker.
        :type payload: dict[str, Any]
        :param user_uid: owner of the task or ``None`` for system tasks.
        :type user_uid: str | None
        :return: whatever :meth:`process` returns.
        :rtype: dict[str, Any]
        """
        return self.process(payload, user_uid=user_uid, task_id=task_id)
