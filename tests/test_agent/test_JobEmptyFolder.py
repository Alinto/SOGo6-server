"""Unit tests for the JobEmptyFolder Agent job (mail module)."""
from unittest.mock import patch

import pytest

from app.module.mail.jobs.JobEmptyFolder import JobEmptyFolder
from app.module.mail.jobs.JobRequestEmptyFolder import JobRequestEmptyFolder

_JOB_MODULE = "app.module.mail.jobs.JobEmptyFolder"
# InterfaceAgentMail is imported at the top of the job module.
_INTERFACE = f"{_JOB_MODULE}.InterfaceAgentMail"


def _payload():
    return {
        "account_id": "0", "folder_path": "Trash",
        "domain": "example.com", "encrypted_password": "enc-pwd",
    }


def test_request_metadata():
    assert JobEmptyFolder.request_class is JobRequestEmptyFolder
    assert JobRequestEmptyFolder.name == "mail.folder.empty"
    assert JobRequestEmptyFolder.resume is False


def test_public_payload_strips_the_encrypted_password():
    # A credential, even encrypted, must not leak through GET /jobs/<id>.
    public = JobEmptyFolder().public_payload(_payload())
    assert public == {"account_id": "0", "folder_path": "Trash", "domain": "example.com"}


def test_process_rejects_missing_user_uid():
    with patch(_INTERFACE) as interface_cls:
        with pytest.raises(ValueError):
            JobEmptyFolder().process(_payload(), user_uid=None, job_id="j-1")
    interface_cls.assert_not_called()


def test_process_empties_the_folder_and_returns_the_count():
    with patch(_INTERFACE) as interface_cls:
        interface_cls.return_value.empty_folder.return_value = {"mails_deleted": 7}
        result = JobEmptyFolder().process(_payload(), user_uid="alice", job_id="j-1")

    assert result == {"mails_deleted": 7}
    assert interface_cls.call_args.args[1:] == ("alice", "example.com", "enc-pwd")
    interface_cls.return_value.empty_folder.assert_called_once_with("0", "Trash")
