"""``JobResultLargeStore`` backend storing the content in the shared Redis cache."""
from __future__ import annotations

import base64
import uuid
from typing import Any

from app.agent.AgentConst import JOB_RESULT_LARGE_KEY_PREFIX
from app.agent.jobs.job_result_large_store.JobResultLargeStorage import JobResultLargeStorage
from app.agent.jobs.job_result_large_store.JobResultLargeStore import JobResultLargeStore
from app.config.settings.ProcessSetting import process_config
from app.service import sogo_cache


class JobResultLargeStoreInMemory(JobResultLargeStore):
    """Backend that stores blobs in Redis under a dedicated ``jobresult:`` key.

    Works in every deployment shape (Flask and the agent share Redis). Practical
    upper bound is a few MB per blob — beyond that, switch to
    :class:`JobResultLargeStoreFile` and a shared volume.
    """

    def save(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Store ``content`` in Redis, base64-encoded.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept with the value for the read path.
        :type content_type: str
        :return: ``{"storage": "in_memory", "key": "jobresult:...", "content_type": ...}``.
        :rtype: dict[str, Any]
        """
        key: str = f"{JOB_RESULT_LARGE_KEY_PREFIX}{uuid.uuid4().hex}"
        payload: dict[str, str] = {
            "content_b64": base64.b64encode(content).decode("ascii"),
            "content_type": content_type,
        }
        sogo_cache().set(
            key, payload,
            ttl=process_config.SOGO_P_AGENT_JOB_STATE_TTL_SECONDS,
        )
        return {
            "storage": JobResultLargeStorage.IN_MEMORY.value,
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
        if ref.get("storage") != JobResultLargeStorage.IN_MEMORY.value:
            raise ValueError(f"Reference is not for in-memory storage: {ref.get('storage')!r}")
        payload = sogo_cache().get(ref["key"], dict)
        if not isinstance(payload, dict):
            raise FileNotFoundError(f"Large result expired or missing: {ref.get('key')!r}")
        return base64.b64decode(payload["content_b64"]), payload["content_type"]
