"""Worker-side Agent job exporting an address book, contact or list as a serialized document.

The serialised document is offloaded to the agent blob store because a whole book can be sizeable.
``JobState.result`` only carries the storage reference plus light metadata. The companion request DTO
lives in ``JobRequestExportContact`` (separate file to keep the enqueue side cycle-free).
"""
from __future__ import annotations

from typing import Any

from app.agent.Agent import agent
from app.agent.jobs.Job import Job, agent_job
from app.config.settings.ProcessSetting import process_config
from app.interface.contact.InterfaceAgentContact import InterfaceAgentContact
from app.module.contact.jobs.JobRequestExportContact import JobRequestExportContact


@agent_job
class JobExportContact(Job):
    """Worker-side counterpart of :class:`JobRequestExportContact`."""

    request_class = JobRequestExportContact

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Serialise the requested book/contact/list and store the result blob.

        :param payload: dict produced by ``JobRequestExportContact.payload``.
        :param user_uid: identity of the owner; ``None`` is rejected.
        :param job_id: Celery-provided id of the running job. Unused here.
        :return: ``{"large_result": "<ref>", "filename": "<name>.<ext>", "size_bytes": int}``.
        :raises ValueError: ``user_uid`` is ``None``.
        """
        if user_uid is None:
            raise ValueError("JobExportContact requires a user_uid")
        req: JobRequestExportContact = JobRequestExportContact(**payload)
        interface: InterfaceAgentContact = InterfaceAgentContact(process_config, user_uid)
        document, filename, media_type = interface.export_document(
            req.kind, req.addressbook_key, req.item_key, req.fmt,
        )
        encoded: bytes = document.encode("utf-8")
        ref: str = agent.get_large_store().save(encoded, media_type)
        return {
            "large_result": ref,
            "filename": filename,
            "size_bytes": len(encoded),
        }
