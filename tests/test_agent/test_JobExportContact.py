"""Unit tests for the JobExportContact Agent job (contact module)."""
from unittest.mock import MagicMock, patch

import pytest

from app.module.contact.jobs.JobExportContact import JobExportContact
from app.module.contact.jobs.JobRequestExportContact import JobRequestExportContact

_JOB_MODULE = "app.module.contact.jobs.JobExportContact"
_INTERFACE = f"{_JOB_MODULE}.InterfaceAgentContact"
_AGENT = f"{_JOB_MODULE}.agent"
_REF = "sogo:file:xyz"


def _payload(kind="addressbook", addressbook_key="k1", item_key=None, fmt="VCARD3"):
    return {"kind": kind, "addressbook_key": addressbook_key, "item_key": item_key, "fmt": fmt}


def _store_agent():
    """An agent whose get_large_store().save returns a ref; returns (agent, store)."""
    store = MagicMock()
    store.save.return_value = _REF
    agent = MagicMock()
    agent.get_large_store.return_value = store
    return agent, store


def test_request_metadata():
    assert JobExportContact.request_class is JobRequestExportContact
    assert JobRequestExportContact.name == "contact.export"
    assert JobRequestExportContact.resume is False


def test_process_rejects_missing_user_uid():
    with pytest.raises(ValueError):
        JobExportContact().process(_payload(), user_uid=None, job_id="j-1")


def test_process_serializes_and_stores_the_result():
    inter = MagicMock()
    inter.export_document.return_value = ("BEGIN:VCARD\r\nEND:VCARD\r\n", "addressbook-k1.vcf", "text/vcard")
    agent, store = _store_agent()
    with patch(_INTERFACE, return_value=inter), patch(_AGENT, agent):
        result = JobExportContact().process(_payload(), user_uid="alice", job_id="j-1")

    inter.export_document.assert_called_once_with("addressbook", "k1", None, "VCARD3")
    encoded = b"BEGIN:VCARD\r\nEND:VCARD\r\n"
    store.save.assert_called_once_with(encoded, "text/vcard")
    assert result == {"large_result": _REF, "filename": "addressbook-k1.vcf", "size_bytes": len(encoded)}
