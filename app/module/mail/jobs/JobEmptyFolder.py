"""Worker-side Agent job permanently deleting every mail of a TRASH or JUNK folder.

Mails are deleted by batches (``MAIL_EMPTY_FOLDER_BATCH_SIZE``): a failing batch is
skipped, the others still go through, then the job fails (its ``error`` holds the
deleted and failed counts). On success, the result carries the number of deleted
mails (small), returned inline in ``JobState.result``. The completion percentage is
published after each batch, exposed as ``progress`` by ``GET /jobs/<id>``.
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
        """Empty the folder by batches and return the number of deleted mails.

        If a batch fails, the other batches are still processed, then the job fails.
        The progress is reported after each batch.

        :param payload: dict produced by ``JobRequestEmptyFolder.payload``.
        :type payload: dict[str, Any]
        :param user_uid: identity of the mailbox owner; ``None`` is rejected.
        :type user_uid: str | None
        :param job_id: Celery-provided id of the running job, used to report the progress.
        :type job_id: str
        :return: ``{"mails_deleted": int}``.
        :rtype: dict[str, Any]
        :raises BugException: ``user_uid`` is ``None``.
        :raises RequestException: ERROR_FOLDER_EMPTY_PARTIAL if at least one batch could not be deleted.
        """
        if user_uid is None:
            raise BugException("JobEmptyFolder requires a user_uid")
        interface: InterfaceAgentMail = InterfaceAgentMail(
            process_config, user_uid, payload["domain"], payload["password"],
        )
        return interface.empty_folder(
            payload["account_id"], payload["folder_path"],
            on_progress=lambda done, total: self.report_progress(job_id, done, total),
        )
