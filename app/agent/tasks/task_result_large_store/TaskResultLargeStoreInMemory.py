"""``TaskResultLargeStore`` backend storing the content in the shared Redis cache."""
from __future__ import annotations

import base64
import uuid
from typing import Any

from app.agent.AgentConst import TASK_RESULT_LARGE_KEY_PREFIX
from app.agent.tasks.task_result_large_store.TaskResultLargeStorage import TaskResultLargeStorage
from app.agent.tasks.task_result_large_store.TaskResultLargeStore import TaskResultLargeStore
from app.config.settings.ProcessSetting import process_config
from app.service import sogo_cache


class TaskResultLargeStoreInMemory(TaskResultLargeStore):
    """Backend that stores blobs in Redis under a dedicated ``taskresult:`` key.

    Works in every deployment shape (Flask and the agent share Redis). Practical
    upper bound is a few MB per blob — beyond that, switch to
    :class:`TaskResultLargeStoreFile` and a shared volume.
    """

    def save(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Store ``content`` in Redis, base64-encoded.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept with the value for the read path.
        :type content_type: str
        :return: ``{"storage": "in_memory", "key": "taskresult:...", "content_type": ...}``.
        :rtype: dict[str, Any]
        """
        key: str = f"{TASK_RESULT_LARGE_KEY_PREFIX}{uuid.uuid4().hex}"
        payload: dict[str, str] = {
            "content_b64": base64.b64encode(content).decode("ascii"),
            "content_type": content_type,
        }
        sogo_cache().set(
            key, payload,
            ttl=process_config.SOGO_P_AGENT_TASK_STATE_TTL_SECONDS,
        )
        return {
            "storage": TaskResultLargeStorage.IN_MEMORY.value,
            "key": key,
            "content_type": content_type,
        }

    def load(self, ref: dict[str, Any]) -> tuple[bytes, str]:
        """Read back the content stored at ``ref["key"]``.

        :param ref: reference dict produced by :meth:`save`.
        :type ref: dict[str, Any]
        :return: ``(content_bytes, content_type)``.
        :rtype: tuple[bytes, str]
        :raises FileNotFoundError: the key has expired or never existed.
        :raises ValueError: ``ref["storage"]`` does not match this backend.
        """
        if ref.get("storage") != TaskResultLargeStorage.IN_MEMORY.value:
            raise ValueError(f"Reference is not for in-memory storage: {ref.get('storage')!r}")
        payload = sogo_cache().get(ref["key"], dict)
        if not isinstance(payload, dict):
            raise FileNotFoundError(f"Large result expired or missing: {ref.get('key')!r}")
        return base64.b64decode(payload["content_b64"]), payload["content_type"]
