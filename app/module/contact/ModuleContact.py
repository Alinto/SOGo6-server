from __future__ import annotations

from typing import TYPE_CHECKING

from app.manager.storage.ClientStorage import ClientStorage
from app.manager.storage.StorageSource import StorageSource
from app.module.contact.ContactConst import (
    ALLOWED_FILE_MIME_TYPES, DEFAULT_ADDRESSBOOK_NAME, FILE_MAX_SIZE_KB, IMPORT_MAX_BYTES,
)
from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.jobs.ContactJobKind import ContactJobKind
from app.module.contact.jobs.JobRequestExportContact import JobRequestExportContact
from app.module.contact.jobs.JobRequestImportContact import JobRequestImportContact
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.ContactImportResult import ContactImportResult
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.module.contact.repository.RepositoryContact import RepositoryContact
from app.module.contact.repository.RepositoryContactList import RepositoryContactList
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
    from app.manager.agent.ClientAgent import ClientAgent
    from app.manager.cache.ClientRedis import ClientRedis
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList
    from app.module.contact.source.ContactSource import ContactSource


class ModuleContact:  # pylint: disable=too-many-public-methods
    """Module for address book and contact operations."""

    def __init__(
        self, process_settings: ProcessSetting,
        cache: ClientRedis | None = None, agent: ClientAgent | None = None,
    ) -> None:
        sogo_db_type: str = f"Client{process_settings.SOGO_P_DB_TYPE}"
        self._db: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=process_settings.get_db_settings(),
        )
        self._db.connect()
        self._cache: ClientRedis | None = cache
        self._agent: ClientAgent | None = agent
        self._sources: ContactSources = ContactSources(self._db)
        self._acl: ContactAclEngine = ContactAclEngine()
        self._file: ClientStorage = import_and_instantiate_manager(
            module_path="app.manager.storage",
            module_and_class_name=f"ClientStorage{process_settings.SOGO_P_STORAGE_TYPE.capitalize()}",
            module_args={"process_setting": process_settings, "source": StorageSource.CONTACT, "db": self._db},
        )

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

    def _get_readable_addressbook(
        self, user: User, key: str, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> ContactSource:
        """Resolve the source for an address book the acting user may read (ACL VIEW level)."""
        source: ContactSource = self.get_addressbook(user, key, user_sources)
        self._acl.check_permission(self._acl.get_share_level(source.addressbook, user), ContactShareLevel.VIEW)
        return source

    def _get_writable_addressbook(
        self, user: User, key: str, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> ContactSource:
        """Resolve the source for an address book the acting user may modify (ACL MODIFY level)."""
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
            if ClientStorage.is_reference(reference) and reference not in current:
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
            if addressbook_key is not None:
                self._get_readable_addressbook(user, addressbook_key, user_sources)  # existence + ACL VIEW
            contacts, total = self._sources.get_contacts(
                user.uid, search=search, offset=offset, limit=limit, sort_by=sort_by,
                order=order, addressbook_key=addressbook_key, user_sources=user_sources, resolve_ab=resolve_ab,
            )
            for contact in contacts:
                if resolve_images:
                    contact.photos = self._file.load_all(contact.photos)
                else:
                    contact.photos = [photo for photo in contact.photos if not ClientStorage.is_reference(photo)]
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
        source: ContactSource = self._get_readable_addressbook(user, addressbook_key, user_sources)
        contact: CardContact | None = source.get_contact_by_key(key)
        if contact is None:
            raise RequestException(error=err.ERROR_CONTACT_NOT_FOUND)
        contact.photos = self._file.load_all(contact.photos)
        return contact

    def _insert_contact(self, source: ContactSource, contact: CardContact) -> CardContact:
        """Persist a new contact into an already-resolved writable source (shared by create and import).

        Photos are offloaded to the file layer; the returned contact keeps the stored references (the
        caller inlines them only when it needs to return them to a client).
        """
        contact.apply_defaults()
        contact.addressbook_key = source.addressbook.require_key
        contact.validate()
        contact.photos = self._save_files([], contact.photos)
        try:
            return source.insert_contact(contact)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception(
                "Unexpected error creating contact in address book %s", source.addressbook.require_key)
            raise RequestException(error=err.ERROR_CONTACT_INSERT_FAILED) from exc

    def _update_contact(self, source: ContactSource, existing: CardContact, contact_update: CardContact) -> None:
        """Persist an update onto an existing contact, preserving its identity (shared by update and import)."""
        # Identity columns are not mutable through an update: a contact cannot be moved to
        # another book nor have its uid/key reassigned by the incoming data.
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
            logger_contact.exception("Unexpected error updating contact %s", existing.key)
            raise RequestException(error=err.ERROR_CONTACT_UPDATE_FAILED) from exc
        self._delete_dropped_files(existing.photos, contact_update.photos)

    def create_contact(
        self, user: User, addressbook_key: str, contact: CardContact,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardContact:
        """Persist a new contact in the address book and return it (uid/display name filled by apply_defaults)."""
        source: ContactSource = self._get_writable_addressbook(user, addressbook_key, user_sources)
        created: CardContact = self._insert_contact(source, contact)
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
        self._update_contact(source, existing, contact_update)
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
            source: ContactSource = self._get_readable_addressbook(user, addressbook_key, user_sources)
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
        source: ContactSource = self._get_readable_addressbook(user, addressbook_key, user_sources)
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
        # nor have its uid/key reassigned by the caller.
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

    #
    # Async import / export (enqueue)
    #
    def enqueue_import(
        self, user: User, kind: ContactJobKind, addressbook_key: str | None, document: str, fmt: str,
    ) -> str:
        """Enqueue a contact import as an Agent job and return the job id.

        Size and ACL checks run synchronously so the caller sees errors immediately. The uploaded
        document is offloaded to the blob store and only its reference travels in the job payload;
        the worker reads it back, deserialises and applies it, then deletes the blob.

        :param user: The user importing the document.
        :param kind: Target scope (whole book / contacts / lists).
        :param addressbook_key: Destination book key for CONTACT/LIST; ``None`` for a new book.
        :param document: Decoded upload content (the byte-accurate size cap is enforced at the API read).
        :param fmt: Source format token (``vcard3`` / ``vcard4`` / ``ldif`` / ``json``).
        :return: id of the enqueued Agent job.
        :raises RequestException: ERROR_CONTACT_IMPORT_TOO_LARGE, ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND,
            or ERROR_JOB_CONCURRENT_LIMIT.
        """
        if self._agent is None:
            raise RuntimeError("ModuleContact.enqueue_import requires a ClientAgent")
        if len(document) > IMPORT_MAX_BYTES:
            raise RequestException(error=err.ERROR_CONTACT_IMPORT_TOO_LARGE)
        if kind is not ContactJobKind.ADDRESSBOOK:
            # CONTACT / LIST target an existing book: fail fast on missing book or no write access.
            self._get_writable_addressbook(user, self._require_key(addressbook_key))
        ref: str = self._agent.get_large_store().save_text(document, "text/plain")
        try:
            request: JobRequestImportContact = JobRequestImportContact(
                kind=kind.value, addressbook_key=addressbook_key, source_ref=ref, fmt=fmt,
            )
            return self._agent.enqueue(request, user_uid=user.uid)
        except Exception:
            # If we couldn't queue the job, the uploaded blob would dangle - drop it.
            self._agent.get_large_store().delete(ref)
            raise

    def enqueue_export(
        self, user: User, kind: ContactJobKind, addressbook_key: str, item_key: str | None, fmt: str,
    ) -> str:
        """Enqueue a contact export as an Agent job and return the job id.

        ACL/existence check on the book runs synchronously (fail fast on 404/403); the worker
        serialises the requested scope and offloads the result to the blob store.

        :param user: The user exporting.
        :param kind: Source scope (whole book / one contact / one list).
        :param addressbook_key: The book key.
        :param item_key: The contact or list key; ``None`` for a whole book.
        :param fmt: Export format token (a ``ContactExportFormat`` member name).
        :return: id of the enqueued Agent job.
        :raises RequestException: ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND or ERROR_JOB_CONCURRENT_LIMIT.
        """
        if self._agent is None:
            raise RuntimeError("ModuleContact.enqueue_export requires a ClientAgent")
        self._get_readable_addressbook(user, addressbook_key)  # existence + ACL VIEW
        request: JobRequestExportContact = JobRequestExportContact(
            kind=kind.value, addressbook_key=addressbook_key, item_key=item_key, fmt=fmt,
        )
        return self._agent.enqueue(request, user_uid=user.uid)

    @staticmethod
    def _require_key(key: str | None) -> str:
        """Return a non-empty key or raise ADDRESSBOOK_NOT_FOUND; an item import needs a destination book."""
        if not key:
            raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
        return key

    #
    # Export
    #
    def get_list_for_export(
        self, user: User, addressbook_key: str, key: str,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> CardList:
        """Return a single list with its member_contacts resolved, ready to serialize as a group card.

        Read access at ACL VIEW level. The list serializers emit members by their contact UID, so the
        members (kept as keys) are resolved to the contacts of the same book here; a member pointing to a
        purged contact is skipped.
        """
        source: ContactSource = self._get_readable_addressbook(user, addressbook_key, user_sources)
        card_list: CardList | None = source.get_list_by_key(key)
        if card_list is None:
            raise RequestException(error=err.ERROR_CONTACT_LIST_NOT_FOUND)
        members: list[CardContact | None] = [source.get_contact_by_key(member) for member in card_list.members]
        card_list.member_contacts = [member for member in members if member is not None]
        return card_list

    def get_addressbook_content(
        self, user: User, key: str, user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> AddressBookContent:
        """Return a book's full content (every contact and list) for export, read access at ACL VIEW level.

        Photos are inlined as data URIs so the exported document is self-contained. Each list's
        member_contacts are populated from the already-loaded contacts (the list serializers emit members
        by their contact UID), so resolving membership costs no extra per-member query.
        """
        try:
            source: ContactSource = self._get_readable_addressbook(user, key, user_sources)
            contacts: list[CardContact] = source.get_contacts()
            for contact in contacts:
                contact.photos = self._file.load_all(contact.photos)
            by_key: dict[str, CardContact] = {contact.key: contact for contact in contacts if contact.key}
            lists: list[CardList] = source.get_lists()
            for card_list in lists:
                card_list.member_contacts = [by_key[member] for member in card_list.members if member in by_key]
            return AddressBookContent(contacts=contacts, lists=lists)
        except RequestException:
            raise
        except Exception as exc:
            logger_contact.exception("Unexpected error reading content of book %s", key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def import_addressbook(
        self, user: User, content: AddressBookContent, name: str,
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> tuple[CardAddressBook, ContactImportResult]:
        """Create a new address book and import a document's full content (contacts + lists) into it.

        Symmetric with the whole-book export: the book is created here (the document carries no book
        identity), then the two internal upserts run. Returns the created book and the counters.
        """
        book: CardAddressBook = self.create_addressbook(
            user, CardAddressBook(user_uid=user.uid, name=name, source_type=CardSourceType.LOCAL), user_sources)
        source: ContactSource = self._get_writable_addressbook(user, book.require_key, user_sources)
        result: ContactImportResult = ContactImportResult()
        self._upsert_contacts(source, content.contacts, result)
        self._upsert_lists(source, content.lists, result)
        return book, result

    def import_contact(
        self, user: User, key: str, contacts: list[CardContact],
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> ContactImportResult:
        """Import contacts into an existing address book, upserting by uid (ACL MODIFY)."""
        source: ContactSource = self._get_writable_addressbook(user, key, user_sources)
        result: ContactImportResult = ContactImportResult()
        self._upsert_contacts(source, contacts, result)
        return result

    def import_list(
        self, user: User, key: str, lists: list[CardList],
        user_sources: dict[str, UserSourceSettingsObj] | None = None,
    ) -> ContactImportResult:
        """Import distribution lists into an existing address book, upserting by uid (ACL MODIFY).

        A list's members must already exist in the book (its member_contacts were linked by the document
        deserializer); a member with no resolvable key is dropped.
        """
        source: ContactSource = self._get_writable_addressbook(user, key, user_sources)
        result: ContactImportResult = ContactImportResult()
        self._upsert_lists(source, lists, result)
        return result

    def _upsert_contacts(
        self, source: ContactSource, contacts: list[CardContact], result: ContactImportResult,
    ) -> None:
        """Upsert each contact by uid into a resolved source; each persisted object gets its key stamped.

        An entry that fails on its own is counted in skipped and never aborts the import.
        """
        for contact in contacts:
            try:
                existing: CardContact | None = source.get_contact_by_uid(contact.uid) if contact.uid else None
                if existing is not None:
                    self._update_contact(source, existing, contact)
                    result.contacts_updated += 1
                else:
                    self._insert_contact(source, contact)
                    result.contacts_inserted += 1
            except RequestException:
                logger_contact.exception("Skipping a contact during import into book %s", source.addressbook.key)
                result.skipped += 1

    def _upsert_lists(
        self, source: ContactSource, lists: list[CardList], result: ContactImportResult,
    ) -> None:
        """Upsert each list by uid; members are resolved from the keys of the contacts persisted this import."""
        for card_list in lists:
            try:
                self._upsert_one_list(source, card_list, result)
            except RequestException:
                logger_contact.exception("Skipping a list during import into book %s", source.addressbook.key)
                result.skipped += 1

    def _upsert_one_list(self, source: ContactSource, card_list: CardList, result: ContactImportResult) -> None:
        """Upsert one parsed list by uid; members come from the keys of the contacts persisted this import."""
        # Members reference parsed contacts now carrying their persisted key; a member whose contact was
        # skipped (insert failed) has no key and is dropped.
        card_list.members = [member.key for member in card_list.member_contacts if member.key]
        existing: CardList | None = source.get_list_by_uid(card_list.uid) if card_list.uid else None
        if existing is not None:
            card_list.id = existing.id
            card_list.key = existing.key
            card_list.uid = existing.uid
            card_list.addressbook_key = existing.addressbook_key
            source.update_list(card_list)
            result.lists_updated += 1
        else:
            card_list.addressbook_key = source.addressbook.require_key
            card_list.uid = card_list.uid or generate_uuid()
            source.insert_list(card_list)
            result.lists_inserted += 1

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
        referenced: set[str] = {value for value in contact_repo.all_photo_values() if ClientStorage.is_reference(value)}
        purged += self._file.purge_orphans(referenced)
        return purged
