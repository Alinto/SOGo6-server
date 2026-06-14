from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.ContactConst import DEFAULT_ADDRESSBOOK_NAME
from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.module.contact.source.ContactSources import ContactSources
from app.utils import errors as err
from app.utils.db.Condition import Order
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_contact
from app.utils.maths.sogo_hash import generate_uuid
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.DomainSettings import UserSourceSettingsObj
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.source.ContactSource import ContactSource


class ModuleContact:
    """Module for address book and contact operations."""

    def __init__(self, process_settings: ProcessSetting, cache: ClientRedis | None = None) -> None:
        sogo_db_type: str = f"Client{process_settings.SOGO_P_DB_TYPE}"
        self._db: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=process_settings.get_db_settings(),
        )
        self._db.connect()
        self._cache: ClientRedis | None = cache
        self._sources: ContactSources = ContactSources(self._db)
        self._acl: ContactAclEngine = ContactAclEngine()

    def __del__(self) -> None:
        if hasattr(self, "_db"):
            self._db.close()

    def create_personal_addressbook(self, user_uid: str, name: str = DEFAULT_ADDRESSBOOK_NAME) -> CardAddressBook:
        """Create and persist the default personal address book for a user.

        Idempotent: if the user already has a default address book, returns it without creating
        a new one. Called at first login alongside the personal calendar provisioning.

        :param user_uid: The user the address book belongs to.
        :param name: Display name of the personal address book.
        :return: The existing or newly created default address book.
        """
        for source in self._sources.get_all(user_uid):
            if source.addressbook.is_default:
                return source.addressbook
        book: CardAddressBook = CardAddressBook(
            user_uid=user_uid, name=name, is_default=True, source_type=CardSourceType.LOCAL,
        )
        book.key = generate_uuid()
        source = self._sources.get(book)
        return source.save_addressbook(book)

    #
    # Address books
    #
    def get_all_addressbooks(
        self, user: User, user_source: UserSourceSettingsObj | None = None,
    ) -> list[CardAddressBook]:
        """Return all address books owned by the user (local DB books; directory when user_source set)."""
        return [source.addressbook for source in self._sources.get_all(user.uid, user_source)]

    def get_addressbook(
        self, user: User, key: str, user_source: UserSourceSettingsObj | None = None,
    ) -> ContactSource:
        """Return the source for an address book, or raise ADDRESSBOOK_NOT_FOUND."""
        source: ContactSource | None = self._sources.get_by_key(user.uid, key, user_source)
        if source is None:
            raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
        return source

    def _require_modify(self, source: ContactSource, user: User) -> None:
        """Enforce that the acting user may modify the source's address book (ACL MODIFY level)."""
        self._acl.check_permission(self._acl.get_share_level(source.addressbook, user), ContactShareLevel.MODIFY)

    def _get_writable_addressbook(
        self, user: User, key: str, user_source: UserSourceSettingsObj | None = None,
    ) -> ContactSource:
        """Resolve the source for an address book the acting user is allowed to modify.

        Access is decided by the ACL engine (owner gets MODIFY; otherwise ERROR_CONTACT_ACCESS_DENIED).
        Resolution is uniform across sources.
        """
        source: ContactSource = self.get_addressbook(user, key, user_source)
        self._require_modify(source, user)
        return source

    def create_addressbook(
        self, user: User, book: CardAddressBook, user_source: UserSourceSettingsObj | None = None,
    ) -> CardAddressBook:
        """Persist a new address book. Generates key and ctag."""
        book.user_uid = user.uid
        book.key = generate_uuid()
        book.ctag = 0
        source: ContactSource = self._sources.get(book, user_source)
        return source.save_addressbook(book)

    def update_addressbook(
        self, user: User, key: str, updates: dict, user_source: UserSourceSettingsObj | None = None,
    ) -> CardAddressBook:
        """Apply updates to an existing address book and persist it."""
        source: ContactSource = self._get_writable_addressbook(user, key, user_source)
        book: CardAddressBook = source.addressbook
        book.apply_update(updates)
        source.update_addressbook(book)
        return book

    def delete_addressbook(
        self, user: User, key: str, hard_delete: bool = False,
        user_source: UserSourceSettingsObj | None = None,
    ) -> None:
        """Delete an address book; its contacts are tombstoned and detached (soft) or removed (hard)."""
        source: ContactSource = self._get_writable_addressbook(user, key, user_source)
        source.delete_addressbook(hard_delete=hard_delete)

    #
    # Contacts
    #
    def get_contacts(
        self, user: User, addressbook_key: str | None = None, search: str | None = None,
        offset: int = 0, limit: int = 0, sort_by: str | None = None, order: Order = Order.ASC,
        resolve_ab: bool = True, user_source: UserSourceSettingsObj | None = None,
    ) -> tuple[list[CardContact], int]:
        """Return a page of contacts plus the total count.

        When addressbook_key is None the search spans all the user's address books (transverse,
        like ModuleCalendar.get_events with calendar_key=None); otherwise it is scoped to one book.
        sort_by must be validated against an allowlist by the caller (it becomes an ORDER BY column);
        the interface restricts it to the sortable contact fields.

        :param user: The authenticated user.
        :param addressbook_key: Opaque key of one address book, or None to span all of them.
        :param search: Optional full-text query.
        :param offset: Number of contacts to skip (pagination).
        :param limit: Maximum number of contacts to return (0 = no limit).
        :param sort_by: Column to sort by, or None for the default (display_name).
        :param order: Sort direction (ascending or descending).
        :param resolve_ab: When True, stamp each contact with its address book name for the response.
        :param user_source: Acting user's source config (None = local DB only).
        :return: A tuple (contacts page, total count matching the filter).
        """
        try:
            return self._sources.get_contacts(
                user.uid, search=search, offset=offset, limit=limit, sort_by=sort_by,
                order=order, addressbook_key=addressbook_key, user_source=user_source, resolve_ab=resolve_ab,
            )
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error fetching contacts (book=%s)", addressbook_key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def _find_source_for_contact(
        self, user: User, key: str, user_source: UserSourceSettingsObj | None = None,
    ) -> tuple[ContactSource, CardContact]:
        """Locate the source and contact owning an opaque contact key across the user's books.

        Backs the flat /contacts/<key> addressing: the contact is resolved without knowing its
        book up front. Raises CONTACT_NOT_FOUND when no source holds it.
        """
        for source in self._sources.get_all(user.uid, user_source):
            contact: CardContact | None = source.get_contact_by_key(key)
            if contact is not None:
                return source, contact
        raise RequestException(error=err.ERROR_CONTACT_NOT_FOUND)

    def get_contact(self, user: User, key: str, user_source: UserSourceSettingsObj | None = None) -> CardContact:
        """Return a single contact by its opaque key across the user's books, or raise CONTACT_NOT_FOUND."""
        _, contact = self._find_source_for_contact(user, key, user_source)
        return contact

    def create_contact(
        self, user: User, addressbook_key: str, contact: CardContact,
        user_source: UserSourceSettingsObj | None = None,
    ) -> CardContact:
        """Persist a new contact in the address book and return it.

        :param user: The authenticated user.
        :param addressbook_key: Opaque key of the destination address book.
        :param contact: The contact to create (uid and display name are filled by apply_defaults).
        :param user_source: Acting user's source config (None = local DB).
        :return: The persisted contact with id and key populated.
        """
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_source)
        contact.apply_defaults()
        contact.addressbook_key = source.addressbook.require_key
        contact.validate()
        try:
            return source.insert_contact(contact)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error creating contact in address book %s", addressbook_key)
            raise RequestException(error=err.ERROR_CONTACT_INSERT_FAILED) from exc

    def update_contact(
        self, user: User, key: str, contact_update: CardContact,
        user_source: UserSourceSettingsObj | None = None,
    ) -> CardContact:
        """Update an existing contact, preserving its identity, and return the persisted result.

        :param user: The authenticated user.
        :param key: Opaque key of the contact to update.
        :param contact_update: The merged contact carrying the new field values.
        :param user_source: Acting user's source config (None = local DB).
        :return: The persisted contact after the update.
        """
        source, existing = self._find_source_for_contact(user, key, user_source)
        self._require_modify(source, user)
        # Identity columns are not mutable through an update: a contact cannot be moved to
        # another book nor have its uid/key reassigned by the request body.
        contact_update.db_id = existing.db_id
        contact_update.key = existing.key
        contact_update.uid = existing.uid
        contact_update.addressbook_key = existing.addressbook_key
        contact_update.validate()
        try:
            source.update_contact(contact_update)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error updating contact %s", key)
            raise RequestException(error=err.ERROR_CONTACT_UPDATE_FAILED) from exc
        refetched: CardContact | None = source.get_contact_by_key(key)
        if refetched is None:
            raise BugException(f"Contact key={key} was updated but could not be fetched back")
        return refetched

    def delete_contact(self, user: User, key: str, user_source: UserSourceSettingsObj | None = None) -> None:
        """Soft-delete a contact by its opaque key across the user's books."""
        source, _ = self._find_source_for_contact(user, key, user_source)
        self._require_modify(source, user)
        try:
            source.delete_contact(key)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error deleting contact %s", key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc
