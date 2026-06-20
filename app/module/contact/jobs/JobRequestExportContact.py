"""Request DTO for the contact export job.

Standalone (not co-located with ``JobExportContact``) so ``ModuleContact`` can import it at
module level to enqueue, without pulling the worker side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest


@dataclass
class JobRequestExportContact(JobRequest):
    """Inputs for a contact export job.

    ``kind`` selects the source scope (whole book / one contact / one list); ``addressbook_key``
    is the book; ``item_key`` is the contact or list key (``None`` for a whole book). ``fmt`` is the
    export format token (a ``ContactExportFormat`` member name) resolved from the Accept header at
    enqueue time, since the worker has no HTTP context.
    """

    name: ClassVar[str] = "contact.export"
    # pylint: disable=duplicate-code
    soft_timeout_seconds: ClassVar[int] = 300
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False

    kind: str = ""
    addressbook_key: str | None = None
    # pylint: enable=duplicate-code
    item_key: str | None = None
    fmt: str = ""

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return {
            "kind": self.kind,
            "addressbook_key": self.addressbook_key,
            "item_key": self.item_key,
            "fmt": self.fmt,
        }
