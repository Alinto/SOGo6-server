from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.ContactConst import ALLOWED_FILE_MIME_TYPES, DEFAULT_ADDRESSBOOK_NAME, FILE_MAX_SIZE_KB
from app.manager.db.DbFileStorage import DbFileStorage
from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.module.contact.repository.RepositoryContact import RepositoryContact
from app.module.contact.repository.RepositoryContactList import RepositoryContactList
from app.module.contact.source.ContactSources import ContactSources
from app.utils import errors as err
from app.utils.db.Condition import Order
from app.utils.exceptions import BugException, RequestException
from app.utils.file.FileAdapter import FileAdapter
from app.utils.file.FileAdapterDatabase import FileAdapterDatabase
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
    from app.module.contact.model.CardList import CardList
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
        self._file: FileAdapter = FileAdapterDatabase(DbFileStorage(self._db))

    def __del__(self) -> None:
        if hasattr(self, "_db"):
            self._db.close()

    def create_personal_addressbook(self, user_uid: str, name: str = DEFAULT_ADDRESSBOOK_NAME) -> CardAddressBook:
        """Create and persist the default personal address book for a user.

        Idempotent: if the user already has a default address book, returns it without creating
        a new one. Called at first login alongside the personal calendar provisioning.
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
        self, user: User, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> list[CardAddressBook]:
        """Return all address books owned by the user (local DB books; directory when user_sources set)."""
        return [source.addressbook for source in self._sources.get_all(user.uid, user_sources)]

    def get_addressbook(
        self, user: User, key: str, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> ContactSource:
        """Return the source for an address book, or raise ADDRESSBOOK_NOT_FOUND."""
        source: ContactSource | None = self._sources.get_by_key(user.uid, key, user_sources)
        if source is None:
            raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
        return source

    def _require_modify(self, source: ContactSource, user: User) -> None:
        """Enforce that the acting user may modify the source's address book (ACL MODIFY level)."""
        self._acl.check_permission(self._acl.get_share_level(source.addressbook, user), ContactShareLevel.MODIFY)

    def _get_writable_addressbook(
        self, user: User, key: str, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> ContactSource:
        """Resolve the source for an address book the acting user may modify.

        Access is decided by the ACL engine (owner gets MODIFY; otherwise ERROR_CONTACT_ACCESS_DENIED).
        """
        source: ContactSource = self.get_addressbook(user, key, user_sources)
        self._require_modify(source, user)
        return source

    def create_addressbook(
        self, user: User, book: CardAddressBook, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardAddressBook:
        """Persist a new address book. Generates key and ctag."""
        book.user_uid = user.uid
        book.key = generate_uuid()
        book.ctag = 0
        source: ContactSource = self._sources.get(book, user_sources)
        return source.save_addressbook(book)

    def update_addressbook(
        self, user: User, key: str, updates: dict, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardAddressBook:
        """Apply updates to an existing address book and persist it."""
        source: ContactSource = self._get_writable_addressbook(user, key, user_sources)
        book: CardAddressBook = source.addressbook
        book.apply_update(updates)
        source.update_addressbook(book)
        return book

    def delete_addressbook(
        self, user: User, key: str, hard_delete: bool = False,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> None:
        """Delete an address book; its contacts are tombstoned and detached (soft) or removed (hard)."""
        source: ContactSource = self._get_writable_addressbook(user, key, user_sources)
        source.delete_addressbook(hard_delete=hard_delete)

    #
    # Contacts
    #
    def _save_files(self, previous: list[str], incoming: list[str]) -> list[str]:
        """Save a contact's inline files (photos) through the file layer, with the contact limits."""
        return self._file.save_all(previous, incoming, FILE_MAX_SIZE_KB * 1024, ALLOWED_FILE_MIME_TYPES)

    def _delete_dropped_files(self, previous: list[str], current: list[str]) -> None:
        """Reclaim the blobs a write stopped using. Call after the row commit, never before: deleting
        first would strand the row on missing bytes if the commit then failed. clean() is the backstop.
        """
        for reference in previous:
            if FileAdapter.is_reference(reference) and reference not in current:
                self._file.delete(reference)

    def get_contacts(
        self, user: User, addressbook_key: str | None = None, search: str | None = None,
        offset: int = 0, limit: int = 0, sort_by: str | None = None, order: Order = Order.ASC,
        resolve_ab: bool = True, resolve_images: bool = True,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> tuple[list[CardContact], int]:
        """Return a page of contacts plus the total count.

        When addressbook_key is None the search spans all the user's address books (transverse,
        like ModuleCalendar.get_events with calendar_key=None); otherwise it is scoped to one book.
        sort_by must be validated against an allowlist by the caller (it becomes an ORDER BY column);
        the interface restricts it to the sortable contact fields.

        :param resolve_ab: When True, stamp each contact with its address book name for the response.
        :param resolve_images: When True, inline stored photos as data URIs; when False, drop the managed
            references (keeping external URIs) so a listing does not load every photo blob from storage.
        :param user_sources: Domain user sources by source_uid (None = local DB).
        :return: A tuple (contacts page, total count matching the filter).
        """
        try:
            contacts, total = self._sources.get_contacts(
                user.uid, search=search, offset=offset, limit=limit, sort_by=sort_by,
                order=order, addressbook_key=addressbook_key, user_sources=user_sources, resolve_ab=resolve_ab,
            )
            for contact in contacts:
                if resolve_images:
                    contact.photos = self._file.load_all(contact.photos)
                else:
                    contact.photos = [photo for photo in contact.photos if not FileAdapter.is_reference(photo)]
            return contacts, total
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error fetching contacts (book=%s)", addressbook_key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def get_contact(
        self, user: User, addressbook_key: str, key: str,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardContact:
        """Return a single contact by key within an address book, or raise CONTACT_NOT_FOUND."""
        source: ContactSource = self.get_addressbook(user, addressbook_key, user_sources)
        contact: CardContact | None = source.get_contact_by_key(key)
        if contact is None:
            raise RequestException(error=err.ERROR_CONTACT_NOT_FOUND)
        contact.photos = self._file.load_all(contact.photos)
        return contact

    def create_contact(
        self, user: User, addressbook_key: str, contact: CardContact,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardContact:
        """Persist a new contact in the address book and return it (uid/display name filled by apply_defaults)."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        contact.apply_defaults()
        contact.addressbook_key = source.addressbook.require_key
        contact.validate()
        contact.photos = self._save_files([], contact.photos)
        try:
            created: CardContact = source.insert_contact(contact)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error creating contact in address book %s", addressbook_key)
            raise RequestException(error=err.ERROR_CONTACT_INSERT_FAILED) from exc
        created.photos = self._file.load_all(created.photos)
        return created

    def update_contact(
        self, user: User, addressbook_key: str, key: str, contact_update: CardContact,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardContact:
        """Update an existing contact, preserving its identity, and return the persisted result."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        existing: CardContact | None = source.get_contact_by_key(key)
        if existing is None:
            raise RequestException(error=err.ERROR_CONTACT_NOT_FOUND)
        # Identity columns are not mutable through an update: a contact cannot be moved to
        # another book nor have its uid/key reassigned by the request body.
        contact_update.db_id = existing.db_id
        contact_update.key = existing.key
        contact_update.uid = existing.uid
        contact_update.addressbook_key = existing.addressbook_key
        contact_update.validate()
        contact_update.photos = self._save_files(existing.photos, contact_update.photos)
        try:
            source.update_contact(contact_update)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error updating contact %s", key)
            raise RequestException(error=err.ERROR_CONTACT_UPDATE_FAILED) from exc
        self._delete_dropped_files(existing.photos, contact_update.photos)
        refetched: CardContact | None = source.get_contact_by_key(key)
        if refetched is None:
            raise BugException(f"Contact key={key} was updated but could not be fetched back")
        refetched.photos = self._file.load_all(refetched.photos)
        return refetched

    def delete_contact(
        self, user: User, addressbook_key: str, key: str,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> None:
        """Soft-delete a contact by key within an address book."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        if source.get_contact_by_key(key) is None:
            raise RequestException(error=err.ERROR_CONTACT_NOT_FOUND)
        try:
            source.delete_contact(key)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error deleting contact %s", key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    #
    # Distribution lists
    #
    def get_all_lists(
        self, user: User, addressbook_key: str, search: str | None = None,
        offset: int = 0, limit: int = 0, sort_by: str | None = None, order: Order = Order.ASC,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> tuple[list[CardList], int]:
        """Return a page of distribution lists of an address book plus the total count.

        Lists are book-scoped (unlike the transverse contact listing): a list belongs to one book.
        """
        try:
            source: ContactSource = self.get_addressbook(user, addressbook_key, user_sources)
            return source.get_lists(search, offset, limit, sort_by, order), source.count_lists(search)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error fetching lists (book=%s)", addressbook_key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def search_all_lists(
        self, user: User, search: str | None = None, limit: int = 0,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> list[CardList]:
        """Return the user's distribution lists across every book, name-filtered and capped (autocomplete).

        Transverse counterpart of get_all_lists, used by recipient autocompletion so a list surfaces
        as a suggestion alongside contacts.
        """
        try:
            return self._sources.search_all_lists(user.uid, search=search, limit=limit, user_sources=user_sources)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error searching lists for user %s", user.uid)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def get_list(
        self, user: User, addressbook_key: str, key: str,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardList:
        """Return a single list by key within an address book (members populated), or raise LIST_NOT_FOUND."""
        source: ContactSource = self.get_addressbook(user, addressbook_key, user_sources)
        card_list: CardList | None = source.get_list_by_key(key)
        if card_list is None:
            raise RequestException(error=err.ERROR_CONTACT_LIST_NOT_FOUND)
        return card_list

    @staticmethod
    def _validate_members(source: ContactSource, member_keys: list[str]) -> None:
        """Ensure every member key is a non-deleted contact of the list's own address book.

        A distribution list references contacts stored in its address book; a member key that does
        not resolve there (unknown, deleted, or from another book) is rejected.
        """
        for member_key in dict.fromkeys(member_keys):
            if source.get_contact_by_key(member_key) is None:
                raise RequestException(error=err.ERROR_CONTACT_LIST_MEMBER_INVALID)

    def create_list(
        self, user: User, addressbook_key: str, card_list: CardList,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardList:
        """Persist a new distribution list in the address book and return it (uid generated here)."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        self._validate_members(source, card_list.members)
        card_list.addressbook_key = source.addressbook.require_key
        card_list.uid = generate_uuid()
        try:
            return source.insert_list(card_list)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error creating list in address book %s", addressbook_key)
            raise RequestException(error=err.ERROR_CONTACT_LIST_INSERT_FAILED) from exc

    def update_list(
        self, user: User, addressbook_key: str, key: str, list_update: CardList,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardList:
        """Update an existing list, preserving its identity, and return the persisted result."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        existing: CardList | None = source.get_list_by_key(key)
        if existing is None:
            raise RequestException(error=err.ERROR_CONTACT_LIST_NOT_FOUND)
        self._validate_members(source, list_update.members)
        # Identity columns are not mutable through an update: a list cannot be moved to another book
        # nor have its uid/key reassigned by the request body.
        list_update.id = existing.id
        list_update.key = existing.key
        list_update.uid = existing.uid
        list_update.addressbook_key = existing.addressbook_key
        try:
            source.update_list(list_update)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error updating list %s", key)
            raise RequestException(error=err.ERROR_CONTACT_LIST_UPDATE_FAILED) from exc
        refetched: CardList | None = source.get_list_by_key(key)
        if refetched is None:
            raise BugException(f"List key={key} was updated but could not be fetched back")
        return refetched

    def delete_list(
        self, user: User, addressbook_key: str, key: str,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> None:
        """Soft-delete a distribution list by key within an address book and clear its membership."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        if source.get_list_by_key(key) is None:
            raise RequestException(error=err.ERROR_CONTACT_LIST_NOT_FOUND)
        try:
            source.delete_list(key)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error deleting list %s", key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def clean(self) -> int:
        """Physically remove soft-deleted rows, dangling membership and orphan media; returns the total reclaimed.

        Global purge (unlike the calendar's per-calendar/user clean): deleting an address book detaches
        its contacts and lists (addressbook_key NULL), so only an is_deleted sweep reaches those
        tombstones. Orphan membership rows and blobs no contact references any more are then reclaimed.
        """
        contact_repo: RepositoryContact = RepositoryContact(self._db)
        list_repo: RepositoryContactList = RepositoryContactList(self._db)
        purged: int = contact_repo.purge_deleted() + list_repo.purge_deleted()
        purged += list_repo.purge_orphan_members(list_repo.all_keys(), contact_repo.all_keys())
        referenced: set[str] = {value for value in contact_repo.all_photo_values() if FileAdapter.is_reference(value)}
        purged += self._file.purge_orphans(referenced)
        return purged
