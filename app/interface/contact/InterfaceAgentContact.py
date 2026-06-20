"""Worker-side interface for the contact module.

Mirrors ``InterfaceApiContactContact`` but for the Agent: no Flask context, no HTTP response
formatting. Reconstructs the User from its uid before instantiating ``ModuleContact``, owns the
import deserializers and export serializers (a job carries only a format token, the worker maps
it back to the right (de)serializer), and dispatches by ``ContactJobKind``.
"""
from __future__ import annotations

import json
from typing import Any, Callable, TYPE_CHECKING

from app.auth.User import User
from app.config.init_config import init_get_user_domain_settings
from app.module.contact.ContactConst import IMPORT_BOOK_NAME_PREFIX
from app.module.contact.jobs.ContactJobKind import ContactJobKind
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.enums.ContactExportFormat import ContactExportFormat
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
from app.module.contact.ModuleContact import ModuleContact
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.service import sogo_cache
from app.utils.datetime.DateTimeUtils import today_iso
from app.utils.errors import ERROR_CONTACT_IMPORT_PARSE_FAILED
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList
    from app.module.contact.model.ContactImportResult import ContactImportResult


class InterfaceAgentContact:
    """Contact interface used by Agent tasks.

    Takes a ``user_uid`` (the only identity the broker carries) and resolves the full ``User``
    before instantiating ``ModuleContact``.
    """

    def __init__(self, process_setting: ProcessSetting, user_uid: str) -> None:
        self.user: User = self._load_user(process_setting, user_uid)
        self.module: ModuleContact = ModuleContact(process_setting, cache=sogo_cache())
        # JSON has no dedicated serializer class: the dict <-> string step is done inline, so the
        # Dict (de)serializers are captured by the JSON closures rather than kept as instance state.
        dict_serializer: AddressBookContentSerializerDict = AddressBookContentSerializerDict()
        dict_deserializer: AddressBookContentDeserializerDict = AddressBookContentDeserializerDict()
        self._export_serializers: dict[ContactExportFormat, Callable[[AddressBookContent], str]] = {
            ContactExportFormat.VCARD4: AddressBookContentSerializerVcard(
                CardContactSerializerVcard4(), CardListSerializerVcard4()).serialize,
            ContactExportFormat.VCARD3: AddressBookContentSerializerVcard(
                CardContactSerializerVcard3(), CardListSerializerVcard3()).serialize,
            ContactExportFormat.LDIF: AddressBookContentSerializerLdif().serialize,
            ContactExportFormat.JSON: lambda content: json.dumps(dict_serializer.serialize(content)),
        }
        self._import_deserializers: dict[str, Callable[[str], AddressBookContent]] = {
            "vcard3": AddressBookContentDeserializerVcard().deserialize,
            "vcard4": AddressBookContentDeserializerVcard().deserialize,
            "ldif": AddressBookContentDeserializerLdif().deserialize,
            "json": lambda document: dict_deserializer.deserialize(json.loads(document)),
        }
        self._result_serializer: ContactImportResultSerializerDict = ContactImportResultSerializerDict()

    def import_document(
        self, kind: str, addressbook_key: str | None, document: str, fmt: str,
    ) -> dict[str, Any]:
        """Deserialise a document and apply it to the target scope, returning the import counters.

        :param kind: a ``ContactJobKind`` value (whole book / contacts / lists).
        :param addressbook_key: destination book key (ignored for a whole-book import, which creates one).
        :param document: the decoded upload content.
        :param fmt: source format token (``vcard3`` / ``vcard4`` / ``ldif`` / ``json``).
        :return: the serialised counters; for a whole-book import, also the created book key and name.
        :raises RequestException: ERROR_CONTACT_IMPORT_PARSE_FAILED when the document is malformed or
            yields nothing importable (so the job fails with a clear error instead of reporting 0 imported).
        :raises ValueError: unknown ``kind`` or ``fmt``.
        """
        job_kind: ContactJobKind = ContactJobKind(kind)
        try:
            content: AddressBookContent = self._import_deserializers[fmt](document)
        except (ValueError, KeyError) as exc:
            # Malformed payload (e.g. invalid JSON) - surface a parse error, not a silent 0 import.
            raise RequestException(error=ERROR_CONTACT_IMPORT_PARSE_FAILED) from exc
        if not self._has_importable(job_kind, content):
            # A document that parses to nothing importable (garbage a lenient vCard/LDIF reader reduced to
            # empty) is a malformed file, not an empty import - fail with a parse error rather than 0 imported.
            raise RequestException(error=ERROR_CONTACT_IMPORT_PARSE_FAILED)
        if job_kind is ContactJobKind.ADDRESSBOOK:
            name: str = f"{IMPORT_BOOK_NAME_PREFIX} ({today_iso()})"
            book, result = self.module.import_addressbook(self.user, content, name)
            payload: dict[str, Any] = self._result_serializer.serialize(result)
            payload["addressbook_key"] = book.key
            payload["addressbook_name"] = book.name
            return payload
        if job_kind is ContactJobKind.CONTACT:
            result = self.module.import_contact(self.user, self._require_key(addressbook_key), content.contacts)
            return self._result_serializer.serialize(result)
        result = self.module.import_list(self.user, self._require_key(addressbook_key), content.lists)
        return self._result_serializer.serialize(result)

    def export_document(
        self, kind: str, addressbook_key: str | None, item_key: str | None, fmt: str,
    ) -> tuple[str, str, str]:
        """Load the requested scope and serialise it, returning ``(document, filename, media_type)``.

        :param kind: a ``ContactJobKind`` value (whole book / one contact / one list).
        :param addressbook_key: the book key.
        :param item_key: the contact or list key (ignored for a whole book).
        :param fmt: a ``ContactExportFormat`` member name.
        :raises ValueError: unknown ``kind`` or ``fmt``.
        """
        export_format: ContactExportFormat = ContactExportFormat[fmt]
        serialize: Callable[[AddressBookContent], str] = self._export_serializers[export_format]
        job_kind: ContactJobKind = ContactJobKind(kind)
        book_key: str = self._require_key(addressbook_key)
        if job_kind is ContactJobKind.ADDRESSBOOK:
            content: AddressBookContent = self.module.get_addressbook_content(self.user, book_key)
            basename: str = f"addressbook-{book_key}"
        elif job_kind is ContactJobKind.CONTACT:
            contact: CardContact = self.module.get_contact(self.user, book_key, self._require_key(item_key))
            content = AddressBookContent(contacts=[contact], lists=[])
            basename = f"contact-{item_key}"
        else:
            card_list: CardList = self.module.get_list_for_export(self.user, book_key, self._require_key(item_key))
            content = AddressBookContent(contacts=[], lists=[card_list])
            basename = f"list-{item_key}"
        body: str = serialize(content)
        return body, f"{basename}.{export_format.extension}", export_format.media_type

    @staticmethod
    def _has_importable(job_kind: ContactJobKind, content: AddressBookContent) -> bool:
        """Return True when the parsed document holds something the target scope can import."""
        if job_kind is ContactJobKind.CONTACT:
            return bool(content.contacts)
        if job_kind is ContactJobKind.LIST:
            return bool(content.lists)
        return bool(content.contacts or content.lists)

    @staticmethod
    def _require_key(key: str | None) -> str:
        """Return a non-empty key or raise; an item job without its key is a malformed payload."""
        if not key:
            raise ValueError("Contact job is missing a required key")
        return key

    @staticmethod
    def _load_user(process_setting: ProcessSetting, user_uid: str) -> User:
        # pylint: disable=duplicate-code
        """Rehydrate a User from its uid. Same shape as the Flask before_request gives."""
        user: User = User(uid=user_uid)
        user.mail = user_uid
        user_domain_settings: dict = init_get_user_domain_settings(user)
        ModuleUserProfile(process_setting, user_domain_settings).get_user_profile(user)
        return user
