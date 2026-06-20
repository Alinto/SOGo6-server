"""Request DTO for the contact import job.

Standalone (not co-located with ``JobImportContact``) so ``ModuleContact`` can import it at
module level to enqueue, without pulling the worker side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest


@dataclass
class JobRequestImportContact(JobRequest):
    """Inputs for a contact import job.

    The uploaded document is offloaded to the blob store before enqueue; only its reference
    (``source_ref``) travels in the payload, not the bytes. ``kind`` selects the target scope
    (whole book / contacts / lists); ``addressbook_key`` is the destination book (``None`` when
    importing a whole book, which is created by the worker); ``fmt`` is the source format token
    (``vcard3`` / ``vcard4`` / ``ldif`` / ``json``).
    """

    name: ClassVar[str] = "contact.import"
    # pylint: disable=duplicate-code
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False

    kind: str = ""
    addressbook_key: str | None = None
    # pylint: enable=duplicate-code
    source_ref: str | None = None
    fmt: str = ""

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return {
            "kind": self.kind,
            "addressbook_key": self.addressbook_key,
            "source_ref": self.source_ref,
            "fmt": self.fmt,
        }
