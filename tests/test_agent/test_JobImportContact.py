"""Unit tests for the JobImportContact Agent job (contact module)."""
from unittest.mock import MagicMock, patch

import pytest

from app.module.contact.jobs.JobImportContact import JobImportContact
from app.module.contact.jobs.JobRequestImportContact import JobRequestImportContact

_JOB_MODULE = "app.module.contact.jobs.JobImportContact"
_INTERFACE = f"{_JOB_MODULE}.InterfaceAgentContact"
_AGENT = f"{_JOB_MODULE}.agent"
_REF = "sogo:file:abc"
_UNSET = object()


def _payload(kind="addressbook", addressbook_key=None, source_ref=_UNSET, fmt="vcard4"):
    ref = _REF if source_ref is _UNSET else source_ref
    return {"kind": kind, "addressbook_key": addressbook_key, "source_ref": ref, "fmt": fmt}


def _store_agent(content=b"BEGIN:VCARD\r\nEND:VCARD\r\n"):
    """An agent whose get_large_store().load_text returns the decoded document; returns (agent, store)."""
    store = MagicMock()
    store.load_text.return_value = content.decode("utf-8")
    agent = MagicMock()
    agent.get_large_store.return_value = store
    return agent, store


def test_request_metadata():
    assert JobImportContact.request_class is JobRequestImportContact
    assert JobRequestImportContact.name == "contact.import"
    assert JobRequestImportContact.resume is False


def test_public_payload_strips_the_source_ref():
    public = JobImportContact().public_payload(_payload(kind="contact", addressbook_key="k1"))
    assert "source_ref" not in public
    assert public == {"kind": "contact", "addressbook_key": "k1", "fmt": "vcard4"}


def test_process_rejects_missing_user_uid_but_still_drops_the_blob():
    agent, store = _store_agent()
    with patch(_AGENT, agent):
        with pytest.raises(ValueError):
            JobImportContact().process(_payload(), user_uid=None, job_id="j-1")
    store.delete.assert_called_once_with(_REF)


def test_process_rejects_missing_source_ref():
    with pytest.raises(ValueError):
        JobImportContact().process(_payload(source_ref=None), user_uid="alice", job_id="j-1")


def test_process_loads_imports_and_deletes_the_blob():
    inter = MagicMock()
    inter.import_document.return_value = {"contacts_inserted": 1, "lists_inserted": 0, "skipped": 0}
    agent, store = _store_agent()
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, agent):
        result = JobImportContact().process(
            _payload(kind="contact", addressbook_key="k9", fmt="ldif"), user_uid="alice", job_id="j-1")

    assert result == {"contacts_inserted": 1, "lists_inserted": 0, "skipped": 0}
    store.load_text.assert_called_once_with(_REF)
    inter.import_document.assert_called_once_with("contact", "k9", "BEGIN:VCARD\r\nEND:VCARD\r\n", "ldif")
    store.delete.assert_called_once_with(_REF)


def test_process_deletes_the_blob_even_on_failure():
    inter = MagicMock()
    inter.import_document.side_effect = RuntimeError("boom")
    agent, store = _store_agent(b"BEGIN:VCARD")
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, agent):
        with pytest.raises(RuntimeError):
            JobImportContact().process(_payload(), user_uid="alice", job_id="j-1")
    store.delete.assert_called_once_with(_REF)
