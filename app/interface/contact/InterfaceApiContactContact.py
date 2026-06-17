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
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.model.enums.ContactExportFormat import ContactExportFormat
from app.module.contact.serializer.AddressBookContentSerializerLdif import AddressBookContentSerializerLdif
from app.module.contact.serializer.AddressBookContentSerializerVcard import AddressBookContentSerializerVcard
from app.module.contact.serializer.CardAddressBookSerializerDict import CardAddressBookSerializerDict
from app.module.contact.serializer.CardAddressBooksSerializerList import CardAddressBooksSerializerList
from app.module.contact.serializer.CardContactAutocompleteSerializerList import CardContactAutocompleteSerializerList
from app.module.contact.serializer.CardListAutocompleteSerializerList import CardListAutocompleteSerializerList
from app.module.contact.serializer.CardContactDeserializerDict import CardContactDeserializerDict
from app.module.contact.serializer.CardListDeserializerDict import CardListDeserializerDict
from app.module.contact.serializer.CardListSerializerDict import CardListSerializerDict
from app.module.contact.serializer.CardListsSerializerList import CardListsSerializerList
from app.module.contact.serializer.CardListSerializerVcard3 import CardListSerializerVcard3
from app.module.contact.serializer.CardListSerializerVcard4 import CardListSerializerVcard4
from app.module.contact.serializer.CardContactSerializerDict import CardContactSerializerDict
from app.module.contact.serializer.CardContactSerializerVcard3 import CardContactSerializerVcard3
from app.module.contact.serializer.CardContactSerializerVcard4 import CardContactSerializerVcard4
from app.module.contact.serializer.CardContactsSerializerList import CardContactsSerializerList
from app.service import sogo_cache
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.db.Condition import Order
from app.utils.errors import ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED, ERROR_CONTACT_JSON_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.auth.User import User
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList
    from app.module.contact.source.ContactSource import ContactSource
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs, CustomPaginateResponse
    from app.utils.serializer.Serializer import Serializer


class InterfaceApiContactContact:  # pylint: disable=too-many-instance-attributes
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
        self.module: ModuleContact = ModuleContact(process_setting, cache=sogo_cache())
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
        # Single contacts and lists export as one-item documents through these same serializers, so the
        # LDIF version header and the vCard concatenation rules live in one place (see export_contact/list).
        self._book_export_serializers: dict[ContactExportFormat, Serializer[AddressBookContent, str]] = {
            ContactExportFormat.VCARD4: AddressBookContentSerializerVcard(
                CardContactSerializerVcard4(), CardListSerializerVcard4()),
            ContactExportFormat.VCARD3: AddressBookContentSerializerVcard(
                CardContactSerializerVcard3(), CardListSerializerVcard3()),
            ContactExportFormat.LDIF: AddressBookContentSerializerLdif(),
        }

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
    # Export
    #
    def export_addressbook(
        self, key: str, accept: str,
    ) -> tuple[str, int, dict[str, str]] | tuple[dict[str, Any], int]:
        """Export an address book (its contacts and lists) as a single vCard or LDIF document.

        :param key: Opaque address book key.
        :param accept: Raw HTTP Accept header value; the export serialization is negotiated from it.
        :return: A tuple ``(body, 200, headers)`` for Flask on success (file download headers set), or
            the standard error envelope on failure (406 when the requested format is unsupported).
        """
        try:
            export_format: ContactExportFormat | None = self._negotiate_export_format(accept)
            if export_format is None:
                return create_api_base_response(None, ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED)
            content: AddressBookContent = self.module.get_addressbook_content(self.user, key)
            body: str = self._book_export_serializers[export_format].serialize(content)
            return body, 200, self._download_headers(export_format, f"addressbook-{key}")
        except RequestException as ex:
            logger_api.error("export_addressbook failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def export_contact(
        self, addressbook_key: str, key: str, accept: str,
    ) -> tuple[str, int, dict[str, str]] | tuple[dict[str, Any], int]:
        """Export a single contact as a one-item vCard or LDIF document, serialization negotiated from Accept."""
        try:
            export_format: ContactExportFormat | None = self._negotiate_export_format(accept)
            if export_format is None:
                return create_api_base_response(None, ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED)
            contact: CardContact = self.module.get_contact(self.user, addressbook_key, key)
            content: AddressBookContent = AddressBookContent(contacts=[contact], lists=[])
            body: str = self._book_export_serializers[export_format].serialize(content)
            return body, 200, self._download_headers(export_format, f"contact-{key}")
        except RequestException as ex:
            logger_api.error("export_contact failed for user %s book %s key %s: %s",
                             self.user.uid, addressbook_key, key, ex)
            return create_api_base_response(None, ex.error)

    def export_list(
        self, addressbook_key: str, key: str, accept: str,
    ) -> tuple[str, int, dict[str, str]] | tuple[dict[str, Any], int]:
        """Export a single distribution list as a one-item vCard or LDIF document, negotiated from Accept."""
        try:
            export_format: ContactExportFormat | None = self._negotiate_export_format(accept)
            if export_format is None:
                return create_api_base_response(None, ERROR_CONTACT_EXPORT_FORMAT_UNSUPPORTED)
            card_list: CardList = self.module.get_list_for_export(self.user, addressbook_key, key)
            content: AddressBookContent = AddressBookContent(contacts=[], lists=[card_list])
            body: str = self._book_export_serializers[export_format].serialize(content)
            return body, 200, self._download_headers(export_format, f"list-{key}")
        except RequestException as ex:
            logger_api.error("export_list failed for user %s book %s key %s: %s",
                             self.user.uid, addressbook_key, key, ex)
            return create_api_base_response(None, ex.error)

    @staticmethod
    def _negotiate_export_format(accept: str) -> ContactExportFormat | None:
        """Resolve the export format from an Accept header value.

        Empty or wildcard accepts default to vCard 3.0 - the only dialect Apple / Google / Outlook all
        import reliably (vCard 4.0 imports blank in Apple Contacts). text/ldif selects LDIF; a text/vcard
        accept yields 4.0 only when it carries version=4, else 3.0. Any other explicit type yields None so
        the caller answers 406.
        """
        value: str = accept.lower()
        if not value or "*/*" in value:
            return ContactExportFormat.VCARD3
        if "text/ldif" in value:
            return ContactExportFormat.LDIF
        if "text/vcard" in value or "text/x-vcard" in value:
            return ContactExportFormat.VCARD4 if "version=4" in value else ContactExportFormat.VCARD3
        return None

    @staticmethod
    def _download_headers(export_format: ContactExportFormat, basename: str) -> dict[str, str]:
        """Build the content type and attachment headers so the response downloads as a file."""
        return {
            "Content-Type": export_format.media_type,
            "Content-Disposition": f'attachment; filename="{basename}.{export_format.extension}"',
        }
