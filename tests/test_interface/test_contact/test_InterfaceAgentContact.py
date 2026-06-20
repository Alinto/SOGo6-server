"""Unit tests for InterfaceAgentContact - the worker-side import/export (deserialize + serialize + dispatch)."""
import json
from unittest.mock import MagicMock

import pytest

from app.interface.contact.InterfaceAgentContact import InterfaceAgentContact
from app.module.contact.jobs.ContactJobKind import ContactJobKind
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardList import CardList
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.ContactImportResult import ContactImportResult
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.model.enums.ContactExportFormat import ContactExportFormat
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.AddressBookContentDeserializerDict import AddressBookContentDeserializerDict
from app.module.contact.serializer.AddressBookContentDeserializerLdif import AddressBookContentDeserializerLdif
from app.module.contact.serializer.AddressBookContentDeserializerVcard import AddressBookContentDeserializerVcard
from app.module.contact.serializer.AddressBookContentSerializerDict import AddressBookContentSerializerDict
from app.module.contact.serializer.AddressBookContentSerializerLdif import AddressBookContentSerializerLdif
from app.module.contact.serializer.AddressBookContentSerializerVcard import AddressBookContentSerializerVcard
from app.module.contact.serializer.CardContactSerializerVcard3 import CardContactSerializerVcard3
from app.module.contact.serializer.CardContactSerializerVcard4 import CardContactSerializerVcard4
from app.module.contact.serializer.CardListSerializerVcard3 import CardListSerializerVcard3
from app.module.contact.serializer.CardListSerializerVcard4 import CardListSerializerVcard4
from app.module.contact.serializer.ContactImportResultSerializerDict import ContactImportResultSerializerDict


def _build_agent():
    inter = object.__new__(InterfaceAgentContact)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.module = MagicMock()
    dict_serializer = AddressBookContentSerializerDict()
    dict_deserializer = AddressBookContentDeserializerDict()
    vcard_deserializer = AddressBookContentDeserializerVcard()
    inter._export_serializers = {
        ContactExportFormat.VCARD4: AddressBookContentSerializerVcard(
            CardContactSerializerVcard4(), CardListSerializerVcard4()).serialize,
        ContactExportFormat.VCARD3: AddressBookContentSerializerVcard(
            CardContactSerializerVcard3(), CardListSerializerVcard3()).serialize,
        ContactExportFormat.LDIF: AddressBookContentSerializerLdif().serialize,
        ContactExportFormat.JSON: lambda content: json.dumps(dict_serializer.serialize(content)),
    }
    inter._import_deserializers = {
        "vcard3": vcard_deserializer.deserialize,
        "vcard4": vcard_deserializer.deserialize,
        "ldif": AddressBookContentDeserializerLdif().deserialize,
        "json": lambda document: dict_deserializer.deserialize(json.loads(document)),
    }
    inter._result_serializer = ContactImportResultSerializerDict()
    return inter


def _book_content():
    return AddressBookContent(
        contacts=[CardContact(display_name="Alice", uid="u1"), CardContact(display_name="Bob", uid="u2")],
        lists=[CardList(name="Team", uid="l1", members=[])],
    )


# ========== Import ==========

def test_import_addressbook_parses_content_and_returns_book_identity():
    inter = _build_agent()
    book = CardAddressBook(user_uid="alice", name="Import (today)", key="new-ab", source_type=CardSourceType.LOCAL)
    inter.module.import_addressbook.return_value = (book, ContactImportResult(contacts_inserted=1, lists_inserted=1))
    document = ("BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Alice\r\nUID:u1\r\nEND:VCARD\r\n"
                "BEGIN:VCARD\r\nVERSION:4.0\r\nKIND:group\r\nFN:Team\r\nUID:l1\r\nMEMBER:urn:uuid:u1\r\nEND:VCARD\r\n")
    result = inter.import_document(ContactJobKind.ADDRESSBOOK, None, document, "vcard4")
    assert result["contacts_inserted"] == 1 and result["lists_inserted"] == 1
    assert result["addressbook_key"] == "new-ab" and result["addressbook_name"] == "Import (today)"
    content = inter.module.import_addressbook.call_args.args[1]
    assert [c.display_name for c in content.contacts] == ["Alice"]
    assert [c.uid for c in content.lists[0].member_contacts] == ["u1"]  # member linked


def test_import_contact_ldif():
    inter = _build_agent()
    inter.module.import_contact.return_value = ContactImportResult(contacts_inserted=1)
    document = "dn: cn=Alice,ou=contacts\nobjectClass: inetOrgPerson\ncn: Alice\nsn: A\n"
    inter.import_document(ContactJobKind.CONTACT, "k1", document, "ldif")
    assert inter.module.import_contact.call_args.args[1] == "k1"
    contacts = inter.module.import_contact.call_args.args[2]
    assert [c.display_name for c in contacts] == ["Alice"]


def test_import_contact_json_forces_undefined_provenance():
    inter = _build_agent()
    inter.module.import_contact.return_value = ContactImportResult(contacts_inserted=1)
    inter.import_document(
        ContactJobKind.CONTACT, "k1", '{"contacts": [{"display_name": "Eve", "import_format": "vcard4"}]}', "json")
    contacts = inter.module.import_contact.call_args.args[2]
    assert contacts[0].import_format is ContactImportFormat.UNDEFINED  # client value dropped, server-set


def test_import_list_into_existing_book():
    inter = _build_agent()
    inter.module.import_list.return_value = ContactImportResult(lists_inserted=1)
    inter.import_document(ContactJobKind.LIST, "k1", '{"contacts": [], "lists": [{"name": "Team", "uid": "l1"}]}', "json")
    assert inter.module.import_list.call_args.args[1] == "k1"
    assert [l.name for l in inter.module.import_list.call_args.args[2]] == ["Team"]


def test_import_malformed_json_raises():
    inter = _build_agent()
    with pytest.raises(json.JSONDecodeError):
        inter.import_document(ContactJobKind.ADDRESSBOOK, None, '{"contacts": [oops', "json")


def test_import_item_without_key_raises():
    inter = _build_agent()
    with pytest.raises(ValueError):
        inter.import_document(ContactJobKind.CONTACT, None, '{"contacts": []}', "json")


# ========== Export ==========

def test_export_addressbook_vcard3():
    inter = _build_agent()
    inter.module.get_addressbook_content.return_value = _book_content()
    body, filename, media_type = inter.export_document(ContactJobKind.ADDRESSBOOK, "k1", None, "VCARD3")
    assert body.count("BEGIN:VCARD") == 3 and "VERSION:3.0" in body
    assert filename == "addressbook-k1.vcf" and media_type == ContactExportFormat.VCARD3.media_type


def test_export_contact_json_is_a_one_item_document():
    inter = _build_agent()
    inter.module.get_contact.return_value = CardContact(display_name="Alice", uid="u1")
    body, filename, _ = inter.export_document(ContactJobKind.CONTACT, "k1", "u1", "JSON")
    assert filename == "contact-u1.json"
    parsed = json.loads(body)
    assert [c["display_name"] for c in parsed["contacts"]] == ["Alice"]
    assert "key" not in parsed["contacts"][0]  # portable


def test_export_list_as_group_card():
    inter = _build_agent()
    inter.module.get_list_for_export.return_value = CardList(
        name="Team", uid="l1", member_contacts=[CardContact(uid="m1")])
    body, filename, _ = inter.export_document(ContactJobKind.LIST, "k1", "l1", "VCARD3")
    assert "KIND:group" in body and "MEMBER:urn:uuid:m1" in body
    assert filename == "list-l1.vcf"
