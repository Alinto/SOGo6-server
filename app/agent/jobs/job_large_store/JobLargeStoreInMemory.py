"""``JobLargeStore`` backend storing the content in the shared Redis cache."""
from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING

from app.agent.AgentConst import JOB_LARGE_KEY_PREFIX
from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef
from app.agent.jobs.job_large_store.JobLargeStore import JobLargeStore
from app.config.settings.ProcessSetting import process_config

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis


class JobLargeStoreInMemory(JobLargeStore):
    """Backend that stores blobs in Redis under a dedicated ``joblarge:`` key.

    Works in every deployment shape (Flask and the agent share Redis). Practical
    upper bound is a few MB per blob - beyond that, switch to
    :class:`JobLargeStoreFile` and a shared volume. The locator is the Redis key.

    The cache is injected at construction so this module stays free of the
    ``service -> ... -> here`` import path.
    """

    def __init__(self, cache: ClientRedis) -> None:
        self._cache: ClientRedis = cache

    def save(self, content: bytes, content_type: str) -> JobLargeRef:
        """Store ``content`` in Redis, base64-encoded.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept on the reference for the read path.
        :type content_type: str
        :return: a reference whose locator is the Redis key.
        :rtype: JobLargeRef
        """
        key: str = f"{JOB_LARGE_KEY_PREFIX}{uuid.uuid4().hex}"
        payload: dict[str, str] = {"content_b64": base64.b64encode(content).decode("ascii")}
        self._cache.set(key, payload, ttl=process_config.SOGO_P_AGENT_JOB_STATE_TTL_SECONDS)
        return JobLargeRef(content_type=content_type, locator=key)

    def load(self, ref: JobLargeRef) -> bytes:
        """Read back the content stored at ``ref.locator``.

        :param ref: reference whose locator is the Redis key.
        :type ref: JobLargeRef
        :return: the decoded blob content.
        :rtype: bytes
        :raises FileNotFoundError: the key has expired or never existed.
        """
        payload: str | list | dict | None = self._cache.get(ref.locator, dict)
        if not isinstance(payload, dict):
            raise FileNotFoundError(f"Large blob expired or missing: {ref.locator!r}")
        return base64.b64decode(payload["content_b64"])

    def delete(self, ref: JobLargeRef) -> None:
        """Drop the Redis key at ``ref.locator``. No-op if already gone.

        :param ref: reference whose locator is the Redis key.
        :type ref: JobLargeRef
        """
        self._cache.delete(ref.locator)
