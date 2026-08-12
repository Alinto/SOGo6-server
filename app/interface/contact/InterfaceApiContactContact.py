from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import (
    CalendarContactSettings,
    CalendarContactSettingsObj,
    UserModuleSettings,
    UserModuleSettingsObj,
)
from app.module.contact.ContactConst import AUTOCOMPLETE_DEFAULT_LIMIT
from app.module.contact.ModuleContact import ModuleContact
from app.module.contact.jobs.ContactJobKind import ContactJobKind
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.model.enums.ContactExportFormat import ContactExportFormat
from app.module.contact.serializer.CardAddressBookSerializerDict import CardAddressBookSerializerDict
from app.module.contact.serializer.CardAddressBooksSerializerList import CardAddressBooksSerializerList
from app.module.contact.serializer.CardContactAutocompleteSerializerList import CardContactAutocompleteSerializerList
from app.module.contact.serializer.CardListAutocompleteSerializerList import CardListAutocompleteSerializerList
from app.module.contact.serializer.CardContactDeserializerDict import CardContactDeserializerDict
from app.module.contact.serializer.CardListDeserializerDict import CardListDeserializerDict
from app.module.contact.serializer.CardListSerializerDict import CardListSerializerDict
from app.module.contact.serializer.CardListsSerializerList import CardListsSerializerList
from app.module.contact.serializer.CardContactSerializerDict import CardContactSerializerDict
from app.module.contact.serializer.CardContactsSerializerList import CardContactsSerializerList
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.service import sogo_agent, sogo_cache
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.db.Condition import Order
from app.utils.errors import (
    ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED,
    ERROR_CONTACT_JSON_PARSE_FAILED,
)
from app.utils.exceptions import RequestException
from app.auth.User import User
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList
    from app.module.contact.model.ContactImportResult import ContactImportResult
    from app.module.contact.source.ContactSource import ContactSource
    from collections.abc import Callable

    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs, CustomPaginateResponse


class InterfaceApiContactContact:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Interface for all contact operations (address books and contacts)."""

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.user: User = user
        self._process_setting: ProcessSetting = process_setting
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(
            user_domain_settings[CalendarContactSettings.subparent]
        )
        self._user_module_settings: UserModuleSettingsObj = UserModuleSettingsObj(
            user_domain_settings[UserModuleSettings.subparent]
        )
        self.module: ModuleContact = ModuleContact(process_setting, cache=sogo_cache(), agent=sogo_agent())
        self._user_module: ModuleUserProfile = ModuleUserProfile(process_setting, user_domain_settings)
        self._addressbook_serializer: CardAddressBookSerializerDict = CardAddressBookSerializerDict()
        self._addressbooks_serializer: CardAddressBooksSerializerList = CardAddressBooksSerializerList()
        self._contact_serializer: CardContactSerializerDict = CardContactSerializerDict()
        self._contacts_serializer: CardContactsSerializerList = CardContactsSerializerList()
        self._contact_deserializer: CardContactDeserializerDict = CardContactDeserializerDict()
        self._autocomplete_serializer: CardContactAutocompleteSerializerList = CardContactAutocompleteSerializerList()
        self._list_autocomplete_serializer: CardListAutocompleteSerializerList = CardListAutocompleteSerializerList()
        self._list_serializer: CardListSerializerDict = CardListSerializerDict()
        self._lists_serializer: CardListsSerializerList = CardListsSerializerList()
        self._list_deserializer: CardListDeserializerDict = CardListDeserializerDict()

    #
    # Address books
    #
    def get_all_addressbooks(self) -> tuple[dict[str, Any], int]:
        """List the address books owned by the current user."""
        try:
            books: list[CardAddressBook] = self.module.get_all_addressbooks(self.user)
            serialized: list[dict[str, Any]] = self._addressbooks_serializer.serialize(books)
            return create_api_base_response({"addressbooks": serialized, "total_count": len(books)})
        except RequestException as ex:
            logger_api.error("get_all_addressbooks failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def get_addressbook(self, key: str) -> tuple[dict[str, Any], int]:
        """Get a single address book by its key."""
        try:
            source: ContactSource = self.module.get_addressbook(self.user, key)
            return create_api_base_response(self._addressbook_serializer.serialize(source.addressbook))
        except RequestException as ex:
            logger_api.error("get_addressbook failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_addressbook(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new local address book."""
        try:
            book: CardAddressBook = CardAddressBook(
                user_uid=self.user.uid,
                name=body["name"],
                description=body.get("description"),
                source_type=CardSourceType.LOCAL,
            )
            created: CardAddressBook = self.module.create_addressbook(self.user, book)
            
            # Add the addressbook key to the user's folders
            if created.key:
                self._user_module.add_folder_key(self.user.uid, "ADDRESSBOOKS", created.key)
            
            return create_api_base_response(self._addressbook_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_addressbook failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def update_addressbook(self, key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to an address book (mutable fields only)."""
        try:
            updated: CardAddressBook = self.module.update_addressbook(self.user, key, body)
            return create_api_base_response(self._addressbook_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("update_addressbook failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def delete_addressbook(self, key: str) -> tuple[dict[str, Any], int]:
        """Delete an address book and all its contacts."""
        try:
            self.module.delete_addressbook(self.user, key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_addressbook failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Contacts
    #
    def get_contacts(
        self, key: str | None, collection_param: CollectionPaginateArgs, search: str | None = None,
    ) -> CustomPaginateResponse:
        """List contacts, optionally scoped to one address book, with search, sort and pagination.

        Pagination, sort field and sort direction come from collection_param; the total count is
        surfaced through the X-Pagination header (built by the pagination decorator) rather than the
        response body. ``search`` is a separate full-text query argument.

        :param key: Address book key, or None to span all the user's books.
        :param collection_param: Parsed pagination and sort arguments from the request.
        :param search: Optional full-text query.
        :return: A tuple (total_count, API response dict, status code).
        """
        try:
            order: Order = Order.DESC if collection_param.sort_order == "desc" else Order.ASC
            contacts, total = self.module.get_contacts(
                self.user,
                addressbook_key=key,
                search=search,
                offset=collection_param.first_item,
                limit=collection_param.page_size,
                sort_by=collection_param.sort_by,
                order=order,
            )
            serialized: list[dict[str, Any]] = self._contacts_serializer.serialize(contacts)
            return total, *create_api_base_response({"contacts": serialized})
        except RequestException as ex:
            logger_api.error("get_contacts failed for user %s book %s: %s", self.user.uid, key, ex)
            return 0, *create_api_base_response(None, ex.error)

    def autocomplete(self, query: str) -> tuple[dict[str, Any], int]:
        """Return lightweight recipient suggestions (contacts one per email, plus distribution lists).

        Below the domain's autocompletion minimum length the result is an empty list rather than an
        error (standard autocomplete behaviour). The search spans all the user's address books (and
        the directory once ContactSourceDirectory is wired); contacts and lists are each capped at
        AUTOCOMPLETE_DEFAULT_LIMIT. A list surfaces as a suggestion carrying its member_count instead
        of an email address.

        :param query: Partial name or email typed by the user.
        :return: API envelope with a ``suggestions`` list, plus HTTP status code.
        """
        try:
            if len(query.strip()) < self._user_module_settings.SOGO_D_AUTOCOMPLETION_MIN_LEN:
                return create_api_base_response({"suggestions": []})
            contacts, _ = self.module.get_contacts(
                self.user, search=query, limit=AUTOCOMPLETE_DEFAULT_LIMIT, resolve_images=False)
            lists = self.module.search_all_lists(self.user, search=query, limit=AUTOCOMPLETE_DEFAULT_LIMIT)
            suggestions: list[dict[str, Any]] = (
                self._autocomplete_serializer.serialize(contacts)
                + self._list_autocomplete_serializer.serialize(lists)
            )
            return create_api_base_response({"suggestions": suggestions})
        except RequestException as ex:
            logger_api.error("autocomplete failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def get_contact(self, addressbook_key: str, key: str) -> tuple[dict[str, Any], int]:
        """Get a single contact by key within an address book."""
        try:
            contact: CardContact = self.module.get_contact(self.user, addressbook_key, key)
            return create_api_base_response(self._contact_serializer.serialize(contact))
        except RequestException as ex:
            logger_api.error("get_contact failed for user %s contact %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_contact(self, addressbook_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new contact in the given address book."""
        try:
            contact: CardContact = self._contact_deserializer.deserialize(body)
            created: CardContact = self.module.create_contact(self.user, addressbook_key, contact)
            return create_api_base_response(self._contact_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_contact failed for user %s book %s: %s", self.user.uid, addressbook_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse contact body for user %s book %s: %s", self.user.uid, addressbook_key, exc)
            return create_api_base_response(None, ERROR_CONTACT_JSON_PARSE_FAILED)

    def patch_contact(self, addressbook_key: str, key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to a contact within an address book."""
        try:
            existing: CardContact = self.module.get_contact(self.user, addressbook_key, key)
            contact_update: CardContact = self._contact_deserializer.deserialize_with_update(existing, body)
            updated: CardContact = self.module.update_contact(self.user, addressbook_key, key, contact_update)
            return create_api_base_response(self._contact_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("patch_contact failed for user %s contact %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse patch body for user %s contact %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_CONTACT_JSON_PARSE_FAILED)

    def delete_contact(self, addressbook_key: str, key: str) -> tuple[dict[str, Any], int]:
        """Delete a contact within an address book."""
        try:
            self.module.delete_contact(self.user, addressbook_key, key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_contact failed for user %s contact %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Distribution lists
    #
    def get_lists(
        self, addressbook_key: str, collection_param: CollectionPaginateArgs, search: str | None = None,
    ) -> CustomPaginateResponse:
        """List the distribution lists of an address book, with search, sort and pagination.

        Lists are book-scoped (unlike the transverse contact listing). Pagination and sort come from
        collection_param; the total count is surfaced through the X-Pagination header.

        :param addressbook_key: Address book key holding the lists.
        :param collection_param: Parsed pagination and sort arguments from the request.
        :param search: Optional name filter.
        :return: A tuple (total_count, API response dict, status code).
        """
        try:
            order: Order = Order.DESC if collection_param.sort_order == "desc" else Order.ASC
            lists, total = self.module.get_all_lists(
                self.user,
                addressbook_key,
                search=search,
                offset=collection_param.first_item,
                limit=collection_param.page_size,
                sort_by=collection_param.sort_by,
                order=order,
            )
            serialized: list[dict[str, Any]] = self._lists_serializer.serialize(lists)
            return total, *create_api_base_response({"lists": serialized})
        except RequestException as ex:
            logger_api.error("get_lists failed for user %s book %s: %s", self.user.uid, addressbook_key, ex)
            return 0, *create_api_base_response(None, ex.error)

    def get_list(self, addressbook_key: str, key: str) -> tuple[dict[str, Any], int]:
        """Get a single distribution list by key within an address book."""
        try:
            card_list: CardList = self.module.get_list(self.user, addressbook_key, key)
            return create_api_base_response(self._list_serializer.serialize(card_list))
        except RequestException as ex:
            logger_api.error("get_list failed for user %s list %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_list(self, addressbook_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new distribution list in the given address book."""
        try:
            card_list: CardList = self._list_deserializer.deserialize(body)
            created: CardList = self.module.create_list(self.user, addressbook_key, card_list)
            return create_api_base_response(self._list_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_list failed for user %s book %s: %s", self.user.uid, addressbook_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse list body for user %s book %s: %s", self.user.uid, addressbook_key, exc)
            return create_api_base_response(None, ERROR_CONTACT_JSON_PARSE_FAILED)

    def patch_list(self, addressbook_key: str, key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to a distribution list within an address book."""
        try:
            existing: CardList = self.module.get_list(self.user, addressbook_key, key)
            list_update: CardList = self._list_deserializer.deserialize_with_update(existing, body)
            updated: CardList = self.module.update_list(self.user, addressbook_key, key, list_update)
            return create_api_base_response(self._list_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("patch_list failed for user %s list %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse patch body for user %s list %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_CONTACT_JSON_PARSE_FAILED)

    def delete_list(self, addressbook_key: str, key: str) -> tuple[dict[str, Any], int]:
        """Delete a distribution list within an address book."""
        try:
            self.module.delete_list(self.user, addressbook_key, key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_list failed for user %s list %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Import / export (async: enqueue an Agent job, return 202 {job_id})
    #
    def import_addressbook(self, document: str, fmt: str) -> tuple[dict[str, Any], int]:
        """Enqueue an import of a document as a NEW address book and return its ``job_id`` (202).

        The caller polls ``GET /jobs/<job_id>`` until SUCCESS; the import counters plus the created
        book key/name are then in the job result.

        :param document: The decoded upload content.
        :param fmt: Source format ('json' / 'vcard3' / 'vcard4' / 'ldif'), validated by the route schema.
        """
        return self._enqueue_import(ContactJobKind.ADDRESSBOOK, None, document, fmt)

    def import_contact(self, key: str, document: str, fmt: str) -> tuple[dict[str, Any], int]:
        """Enqueue an import of contacts into an existing book and return its ``job_id`` (202)."""
        return self._enqueue_import(ContactJobKind.CONTACT, key, document, fmt)

    def import_list(self, key: str, document: str, fmt: str) -> tuple[dict[str, Any], int]:
        """Enqueue an import of distribution lists into an existing book and return its ``job_id`` (202)."""
        return self._enqueue_import(ContactJobKind.LIST, key, document, fmt)

    def _enqueue_import(
        self, kind: ContactJobKind, addressbook_key: str | None, document: str, fmt: str,
    ) -> tuple[dict[str, Any], int]:
        """Offload the document and enqueue an import job; shared by the three import endpoints."""
        try:
            job_id: str = self.module.enqueue_import(
                self.user, kind, addressbook_key, document, fmt,
            )
            return create_api_base_response({"job_id": job_id}, code=202)
        except RequestException as ex:
            logger_api.error("enqueue_import (%s) failed for user %s: %s", kind, self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    #
    # Export (async)
    #
    def export_addressbook(self, key: str, accept: str) -> tuple[dict[str, Any], int]:
        """Enqueue an export of a whole address book and return its ``job_id`` (202).

        The serialization is negotiated from the Accept header at enqueue time (the worker has no
        HTTP context); the caller fetches the document from ``GET /jobs/<job_id>/result``.
        """
        return self._enqueue_export(ContactJobKind.ADDRESSBOOK, key, None, accept)

    def export_contact(self, addressbook_key: str, key: str, accept: str) -> tuple[dict[str, Any], int]:
        """Enqueue an export of a single contact and return its ``job_id`` (202)."""
        return self._enqueue_export(ContactJobKind.CONTACT, addressbook_key, key, accept)

    def export_list(self, addressbook_key: str, key: str, accept: str) -> tuple[dict[str, Any], int]:
        """Enqueue an export of a single distribution list and return its ``job_id`` (202)."""
        return self._enqueue_export(ContactJobKind.LIST, addressbook_key, key, accept)

    def _enqueue_export(
        self, kind: ContactJobKind, addressbook_key: str, item_key: str | None, accept: str,
    ) -> tuple[dict[str, Any], int]:
        """Resolve the export format from Accept and enqueue an export job; shared by the three endpoints."""
        try:
            export_format: ContactExportFormat | None = self._negotiate_export_format(accept)
            if export_format is None:
                return create_api_base_response(None, ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED)
            job_id: str = self.module.enqueue_export(
                self.user, kind, addressbook_key, item_key, export_format.name,
            )
            return create_api_base_response({"job_id": job_id}, code=202)
        except RequestException as ex:
            logger_api.error("enqueue_export (%s) failed for user %s key %s: %s",
                             kind, self.user.uid, addressbook_key, ex)
            return create_api_base_response(None, ex.error)

    @staticmethod
    def _negotiate_export_format(accept: str) -> ContactExportFormat | None:
        """Resolve the export format from an Accept header value.

        Empty or wildcard accepts default to vCard 3.0 - the only dialect Apple / Google / Outlook all
        import reliably (vCard 4.0 imports blank in Apple Contacts). application/json selects JSON,
        text/ldif selects LDIF; a text/vcard accept yields 4.0 only when it carries version=4, else 3.0.
        Any other explicit type yields None so the caller answers 406.
        """
        value: str = accept.lower()
        if not value or "*/*" in value:
            return ContactExportFormat.VCARD3
        if "application/json" in value:
            return ContactExportFormat.JSON
        if "text/ldif" in value:
            return ContactExportFormat.LDIF
        if "text/vcard" in value or "text/x-vcard" in value:
            return ContactExportFormat.VCARD4 if "version=4" in value else ContactExportFormat.VCARD3
        return None
