"""``JobLargeStore`` backend writing the content to the filesystem."""
from __future__ import annotations

import os
import uuid

from app.agent.jobs.job_large_store.JobLargeRef import JobLargeRef
from app.agent.jobs.job_large_store.JobLargeStore import JobLargeStore
from app.config.settings.ProcessSetting import process_config


class JobLargeStoreFile(JobLargeStore):
    """Backend that writes blobs to ``SOGO_P_TMP_PATH``.

    Scales to any blob size but Flask and every agent worker must share the
    directory (single host, or RWX volume in K8s). Otherwise the API cannot
    serve a file written by a different process. The locator is the file path.
    """

    def save(self, content: bytes, content_type: str) -> JobLargeRef:
        """Write ``content`` to a fresh file under ``SOGO_P_TMP_PATH``.

        :param content: raw bytes to store.
        :type content: bytes
        :param content_type: MIME type kept on the reference for the read path.
        :type content_type: str
        :return: a reference whose locator is the written file path.
        :rtype: JobLargeRef
        """
        tmp_dir: str = process_config.SOGO_P_TMP_PATH
        os.makedirs(tmp_dir, exist_ok=True)
        path: str = os.path.join(tmp_dir, f"joblarge-{uuid.uuid4().hex}")
        with open(path, "wb") as fh:
            fh.write(content)
        return JobLargeRef(content_type=content_type, locator=path)

    def load(self, ref: JobLargeRef) -> bytes:
        """Read back the file at ``ref.locator``.

        :param ref: reference to the file to read.
        :type ref: JobLargeRef
        :return: the file content.
        :rtype: bytes
        :raises FileNotFoundError: the file is missing (cleaned up, never written...).
        :raises ValueError: the path escapes ``SOGO_P_TMP_PATH``.
        """
        with open(self._safe_path(ref.locator), "rb") as fh:
            return fh.read()

    def delete(self, ref: JobLargeRef) -> None:
        """Remove the referenced file. No-op if already gone.

        :param ref: reference to the file to remove.
        :type ref: JobLargeRef
        :raises ValueError: the path escapes ``SOGO_P_TMP_PATH``.
        """
        try:
            os.remove(self._safe_path(ref.locator))
        except FileNotFoundError:
            pass

    @staticmethod
    def _safe_path(locator: str) -> str:
        """Return the real locator path, confined to ``SOGO_P_TMP_PATH``.

        Defence in depth: refs are produced server-side today, but never trust a
        stored path blindly - reads and deletes stay inside the tmp directory.
        """
        tmp_root: str = os.path.realpath(process_config.SOGO_P_TMP_PATH)
        real_path: str = os.path.realpath(locator)
        if os.path.commonpath([real_path, tmp_root]) != tmp_root:
            raise ValueError(f"Refusing to touch a path outside the result directory: {locator!r}")
        return real_path
