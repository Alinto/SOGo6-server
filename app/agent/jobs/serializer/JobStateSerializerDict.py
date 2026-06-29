"""Serialises a JobState into the public API view exposed to the job owner."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.agent.jobs.Job import Job
    from app.agent.jobs.JobState import JobState
    from app.manager.agent.ClientAgent import ClientAgent


class JobStateSerializerDict(Serializer["JobState", dict]):
    """JobState -> public dict: only the owner-facing fields, nothing internal.

    Emits exactly ``status`` / ``payload`` / ``result`` / ``error``. Internal fields
    (job_id, name, user_uid, dates, attempts...) are never exposed: this serializer
    IS the public view, it does not rely on a downstream schema to drop them. The
    payload is run through the job's own ``public_payload`` (secrets / large-input
    references stripped) and the ``large_result`` pointer is removed from the result
    (an internal storage locator; the blob is fetched via ``/jobs/<id>/result``).
    """

    def __init__(self, agent: ClientAgent) -> None:
        self._agent: ClientAgent = agent

    def serialize(self, data: JobState) -> dict[str, Any]:
        """Render a JobState as the public dict shown to the job owner.

        :param data: internal job state to expose.
        :type data: JobState
        :return: ``{"status", "payload", "result", "error"}`` only, payload redacted
            and the internal blob pointer dropped.
        :rtype: dict[str, Any]
        """
        handler: Job | None = self._agent.get_job_handler(data.name)
        payload: dict[str, Any] = data.payload or {}
        if handler is not None:
            payload = handler.public_payload(payload)
        result: Any = data.result
        if isinstance(result, dict) and "large_result" in result:
            result = {key: value for key, value in result.items() if key != "large_result"}
        return {
            "status": data.status.value,
            "payload": payload,
            "result": result,
            "error": data.error,
        }
