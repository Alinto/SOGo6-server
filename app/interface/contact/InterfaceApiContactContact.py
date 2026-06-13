from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import CalendarContactSettings, CalendarContactSettingsObj
from app.module.contact.ModuleContact import ModuleContact
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.serializer.AddressBookSerializerDict import AddressBookSerializerDict
from app.module.contact.serializer.AddressBooksSerializerList import AddressBooksSerializerList
from app.module.contact.serializer.ContactDeserializerDict import ContactDeserializerDict
from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict
from app.module.contact.serializer.ContactsSerializerList import ContactsSerializerList
from app.service import sogo_cache
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.db.Condition import Order
from app.utils.errors import ERROR_CONTACT_JSON_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.auth.User import User
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.source.ContactSource import ContactSource
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs, CustomPaginateResponse


class InterfaceApiContactContact:  # pylint: disable=too-many-instance-attributes
    """Interface for all contact operations (address books and contacts)."""

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.user: User = user
        self._process_setting: ProcessSetting = process_setting
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(
            user_domain_settings[CalendarContactSettings.subparent]
        )
        self.module: ModuleContact = ModuleContact(process_setting, cache=sogo_cache())
        self._addressbook_serializer: AddressBookSerializerDict = AddressBookSerializerDict()
        self._addressbooks_serializer: AddressBooksSerializerList = AddressBooksSerializerList()
        self._contact_serializer: ContactSerializerDict = ContactSerializerDict()
        self._contacts_serializer: ContactsSerializerList = ContactsSerializerList()
        self._contact_deserializer: ContactDeserializerDict = ContactDeserializerDict()

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

    def get_contact(self, addressbook_key: str, key: str) -> tuple[dict[str, Any], int]:
        """Get a single contact by key."""
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
        """Apply partial updates to a contact."""
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
        """Delete a contact."""
        try:
            self.module.delete_contact(self.user, addressbook_key, key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_contact failed for user %s contact %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
