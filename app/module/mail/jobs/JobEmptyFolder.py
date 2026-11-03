"""Worker-side Agent job permanently deleting every mail of a TRASH or JUNK folder.

The result carries the number of deleted mails (small), returned inline in
``JobState.result``.
"""
from __future__ import annotations

from typing import Any

from app.agent.jobs.Job import Job, agent_job
from app.config.settings.ProcessSetting import process_config
from app.interface.mail.InterfaceAgentMail import InterfaceAgentMail
from app.module.mail.jobs.JobRequestEmptyFolder import JobRequestEmptyFolder
from app.utils.exceptions import BugException


@agent_job
class JobEmptyFolder(Job):
    """Worker-side counterpart of :class:`JobRequestEmptyFolder`."""

    request_class = JobRequestEmptyFolder

    def public_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Hide ``password`` from the owner view: even encrypted, a credential is never echoed back.

        :param payload: the raw payload stored in ``JobState.payload``.
        :type payload: dict[str, Any]
        :return: a copy of the payload without ``password``.
        :rtype: dict[str, Any]
        """
        return {key: value for key, value in payload.items() if key != "password"}

    def process(
        self, payload: dict[str, Any], *, user_uid: str | None, job_id: str,
    ) -> dict[str, Any]:
        """Empty the folder and return the number of permanently deleted mails.

        :param payload: dict produced by ``JobRequestEmptyFolder.payload``.
        :type payload: dict[str, Any]
        :param user_uid: identity of the mailbox owner; ``None`` is rejected.
        :type user_uid: str | None
        :param job_id: Celery-provided id of the running job. Unused here.
        :type job_id: str
        :return: ``{"mails_deleted": int}``.
        :rtype: dict[str, Any]
        :raises BugException: ``user_uid`` is ``None``.
        """
        if user_uid is None:
            raise BugException("JobEmptyFolder requires a user_uid")
        interface: InterfaceAgentMail = InterfaceAgentMail(
            process_config, user_uid, payload["domain"], payload["password"],
        )
        return interface.empty_folder(payload["account_id"], payload["folder_path"])
