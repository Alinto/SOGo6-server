"""Worker-side Agent job importing an uploaded document into an address book.

The uploaded document is read back from the agent blob store (saved by the API before enqueue),
deserialised, applied to the book, then deleted - an input blob has no reason to outlive its
consumption. The result carries the import counters (small), returned inline in ``JobState.result``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agent.Agent import agent
from app.agent.jobs.Job import Job, agent_job
from app.config.settings.ProcessSetting import process_config
from app.interface.contact.InterfaceAgentContact import InterfaceAgentContact
from app.module.contact.jobs.JobRequestImportContact import JobRequestImportContact

if TYPE_CHECKING:
    from app.manager.storage.ClientStorage import ClientStorage


@agent_job
class JobImportContact(Job):
    """Worker-side counterpart of :class:`JobRequestImportContact`."""

    request_class = JobRequestImportContact

    def public_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Hide ``source_ref`` from the owner view: it is an internal blob pointer of no use to the client."""
        return {key: value for key, value in payload.items() if key != "source_ref"}

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Deserialise the uploaded document, apply it to the book and return the import counters.

        :param payload: dict produced by ``JobRequestImportContact.payload``.
        :param user_uid: identity of the book owner; ``None`` is rejected.
        :param job_id: Celery-provided id of the running job. Unused here.
        :return: the serialised import counters (plus the created book key/name for a whole-book import).
        :raises ValueError: ``user_uid`` is ``None`` or the request carries no ``source_ref``.
        """
        source_ref: str | None = payload.get("source_ref")
        if not source_ref:
            raise ValueError("JobImportContact requires a source_ref")
        store: ClientStorage = agent.get_large_store()
        try:
            # An input blob is single-use: once we hold its ref, any failure below
            # (including a missing user_uid) must still drop it - hence inside the try.
            if user_uid is None:
                raise ValueError("JobImportContact requires a user_uid")
            document: str = store.load_text(source_ref)
            interface: InterfaceAgentContact = InterfaceAgentContact(process_config, user_uid)
            return interface.import_document(
                payload["kind"], payload.get("addressbook_key"), document, payload["fmt"],
            )
        finally:
            store.delete(source_ref)
