"""Request DTO for the empty mail folder job.

Standalone (not co-located with ``JobEmptyFolder``) so ``ModuleMail`` can
import it at module level to enqueue, without pulling the worker side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.agent.jobs.JobRequest import JobRequest


@dataclass
class JobRequestEmptyFolder(JobRequest):
    """Inputs for an empty mail folder job.

    The worker has no HTTP session: it needs the user's credentials to log in to
    the mail server. ``password`` is the user's password **encrypted** with
    ``encrypt_password`` - never the clear text - and is hidden from the job read
    API by ``JobEmptyFolder.public_payload``.
    """

    name: ClassVar[str] = "mail.folder.empty"
    soft_timeout_seconds: ClassVar[int] = 600
    max_try: ClassVar[int] = 1
    resume: ClassVar[bool] = False

    account_id: str = ""
    folder_path: str = ""
    domain: str = ""
    password: str = ""

    def payload(self) -> dict[str, Any]:
        """Serialise dataclass fields into the dict sent through the broker."""
        return {
            "account_id": self.account_id,
            "folder_path": self.folder_path,
            "domain": self.domain,
            "password": self.password,
        }
