"""User-facing API interface for Agent job results.

Today exposes the read and download endpoints for jobs owned by the current
user. Every method filters on ``g.user.uid`` so a user can only see / fetch
their own jobs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agent.jobs.JobStatus import JobStatus
from app.agent.jobs.job_result_large_store.JobResultLargeStore import JobResultLargeStore
from app.service import sogo_agent
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.errors import (
    ERROR_JOB_FORBIDDEN,
    ERROR_JOB_NOT_FOUND,
    ERROR_JOB_NOT_READY,
    ERROR_JOB_NO_RESULT,
)
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.auth.User import User


class InterfaceApiJob:
    """Read-side interface for Agent jobs owned by the current user."""

    def __init__(self, user: User) -> None:
        self.user: User = user

    def get_job(self, job_id: str) -> tuple[dict[str, Any], int]:
        """Return the JobState envelope for a job owned by the current user.

        :param job_id: id of the job to read.
        :type job_id: str
        :return: API envelope with the serialised JobState, or an error envelope
            (404 unknown, 403 not-owner).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            agent = sogo_agent()
            state = agent.get(job_id)
            if state is None:
                raise RequestException(error=ERROR_JOB_NOT_FOUND)
            if state.user_uid != self.user.uid:
                raise RequestException(error=ERROR_JOB_FORBIDDEN)
            data = state.to_dict()
            # Let the job redact any sensitive field from its payload before exposing it.
            handler = agent.get_job_handler(state.name)
            if handler is not None:
                data["payload"] = handler.public_payload(data.get("payload") or {})
            return create_api_base_response(data)
        except RequestException as ex:
            logger_api.error(
                "get_job failed for user %s job %s: %s",
                self.user.uid, job_id, ex.error.c,
            )
            return create_api_base_response(None, ex.error)

    def get_result(
        self, job_id: str, *, download: bool = False,
    ) -> tuple[bytes, int, dict[str, str]] | tuple[dict[str, Any], int]:
        """Serve the large result blob attached to a completed job.

        The payload is sent with its native Content-Type (text/calendar,
        application/json, …). The ``download`` flag toggles the
        Content-Disposition: attachment header so browsers trigger a file save
        rather than rendering the body inline.

        Errors map to dedicated HTTP statuses (404 unknown, 403 not-owner,
        409 not ready, 410 no result).

        :param job_id: id of the job whose result is requested.
        :type job_id: str
        :param download: when true, set Content-Disposition: attachment.
            Defaults to inline.
        :type download: bool
        :return: ``(payload_bytes, 200, headers)`` on success or the standard
            error envelope.
        :rtype: tuple[bytes, int, dict[str, str]] | tuple[dict[str, Any], int]
        """
        try:
            state = sogo_agent().get(job_id)
            if state is None:
                raise RequestException(error=ERROR_JOB_NOT_FOUND)
            if state.user_uid != self.user.uid:
                raise RequestException(error=ERROR_JOB_FORBIDDEN)
            if state.status != JobStatus.SUCCESS:
                raise RequestException(error=ERROR_JOB_NOT_READY)
            result: dict[str, Any] = state.result or {}
            ref: dict[str, Any] | None = result.get("large_result")
            if not ref:
                raise RequestException(error=ERROR_JOB_NO_RESULT)
            try:
                payload, content_type = JobResultLargeStore.load_ref(ref)
            except (FileNotFoundError, ValueError, OSError) as exc:
                # The result has expired, been cleaned up, or is unreachable (e.g. a
                # FILE backend whose directory is not shared with this process).
                logger_api.error(
                    "get_result: large result unreadable for job %s: %s", job_id, exc,
                )
                raise RequestException(error=ERROR_JOB_NO_RESULT) from exc
            headers: dict[str, str] = {"Content-Type": content_type}
            if download:
                filename: str = result.get("filename") or f"{job_id}.bin"
                headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            return payload, 200, headers
        except RequestException as ex:
            logger_api.error(
                "get_result failed for user %s job %s: %s",
                self.user.uid, job_id, ex.error.c,
            )
            return create_api_base_response(None, ex.error)
