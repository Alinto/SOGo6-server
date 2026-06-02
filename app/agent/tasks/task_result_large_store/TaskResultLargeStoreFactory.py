"""Factory returning the concrete ``TaskResultLargeStore`` for this process."""
from __future__ import annotations

from app.agent.AgentConst import TASK_RESULT_LARGE_STORAGE
from app.agent.tasks.task_result_large_store.TaskResultLargeStorage import TaskResultLargeStorage
from app.agent.tasks.task_result_large_store.TaskResultLargeStore import TaskResultLargeStore
from app.agent.tasks.task_result_large_store.TaskResultLargeStoreFile import TaskResultLargeStoreFile
from app.agent.tasks.task_result_large_store.TaskResultLargeStoreInMemory import TaskResultLargeStoreInMemory


def get_large_store() -> TaskResultLargeStore:
    """Return the store matching the value of ``TASK_RESULT_LARGE_STORAGE``.

    The stores are stateless, so instantiating one on each call is cheap. Callers
    typically hold the result for the duration of a single ``save`` or ``load``.

    :return: a fresh store instance for the configured backend.
    :rtype: TaskResultLargeStore
    """
    if TASK_RESULT_LARGE_STORAGE == TaskResultLargeStorage.FILE:
        return TaskResultLargeStoreFile()
    return TaskResultLargeStoreInMemory()
