"""``TaskResultLargeStore`` backend writing the content to the filesystem."""
from __future__ import annotations

import os
import uuid
from typing import Any

from app.agent.tasks.task_result_large_store.TaskResultLargeStorage import TaskResultLargeStorage
from app.agent.tasks.task_result_large_store.TaskResultLargeStore import TaskResultLargeStore
from app.config.settings.ProcessSetting import process_config


class TaskResultLargeStoreFile(TaskResultLargeStore):
    """Backend that writes blobs to ``SOGO_P_TMP_PATH``.

    Scales to any blob size but Flask and every agent worker must share the
    directory (single host, or RWX volume in K8s). Otherwise the API cannot
    serve a file written by a different process.
    """

    def save(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Write ``content`` to a fresh file under ``SOGO_P_TMP_PATH``.

        :param content: raw bytes to write.
        :type content: bytes
        :param content_type: MIME type carried in the reference dict.
        :type content_type: str
        :return: ``{"storage": "file", "path": "/.../taskresult-...", "content_type": ...}``.
        :rtype: dict[str, Any]
        """
        tmp_dir: str = process_config.SOGO_P_TMP_PATH
        os.makedirs(tmp_dir, exist_ok=True)
        path: str = os.path.join(tmp_dir, f"taskresult-{uuid.uuid4().hex}")
        with open(path, "wb") as fh:
            fh.write(content)
        return {
            "storage": TaskResultLargeStorage.FILE.value,
            "path": path,
            "content_type": content_type,
        }

    def load(self, ref: dict[str, Any]) -> tuple[bytes, str]:
        """Read back the file referenced by ``ref["path"]``.

        :param ref: reference dict produced by :meth:`save`.
        :type ref: dict[str, Any]
        :return: ``(content_bytes, content_type)``.
        :rtype: tuple[bytes, str]
        :raises FileNotFoundError: the file is missing (cleaned up, never written…).
        :raises ValueError: ``ref["storage"]`` does not match this backend.
        """
        if ref.get("storage") != TaskResultLargeStorage.FILE.value:
            raise ValueError(f"Reference is not for file storage: {ref.get('storage')!r}")
        path: str = ref["path"]
        with open(path, "rb") as fh:
            return fh.read(), ref["content_type"]
