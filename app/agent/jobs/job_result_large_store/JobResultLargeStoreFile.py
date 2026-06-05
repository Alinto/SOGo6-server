"""``JobResultLargeStore`` backend writing the content to the filesystem."""
from __future__ import annotations

import os
import uuid
from typing import Any

from app.agent.jobs.job_result_large_store.JobResultLargeStorage import JobResultLargeStorage
from app.agent.jobs.job_result_large_store.JobResultLargeStore import JobResultLargeStore
from app.config.settings.ProcessSetting import process_config


class JobResultLargeStoreFile(JobResultLargeStore):
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
        :return: ``{"storage": "file", "path": "/.../jobresult-...", "content_type": ...}``.
        :rtype: dict[str, Any]
        """
        tmp_dir: str = process_config.SOGO_P_TMP_PATH
        os.makedirs(tmp_dir, exist_ok=True)
        path: str = os.path.join(tmp_dir, f"jobresult-{uuid.uuid4().hex}")
        with open(path, "wb") as fh:
            fh.write(content)
        return {
            "storage": JobResultLargeStorage.FILE.value,
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
        :raises ValueError: ``ref["storage"]`` does not match this backend, or the
            path escapes ``SOGO_P_TMP_PATH``.
        """
        if ref.get("storage") != JobResultLargeStorage.FILE.value:
            raise ValueError(f"Reference is not for file storage: {ref.get('storage')!r}")
        path: str = ref["path"]
        # Defence in depth: refs are produced server-side today, but never trust a
        # stored path blindly — confine reads to the configured tmp directory.
        tmp_root: str = os.path.realpath(process_config.SOGO_P_TMP_PATH)
        real_path: str = os.path.realpath(path)
        if os.path.commonpath([real_path, tmp_root]) != tmp_root:
            raise ValueError(f"Refusing to read outside the result directory: {path!r}")
        with open(real_path, "rb") as fh:
            return fh.read(), ref["content_type"]
