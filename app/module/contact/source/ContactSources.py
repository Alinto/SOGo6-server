from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.repository.RepositoryAddressBook import RepositoryAddressBook
from app.module.contact.source.ContactSourceDb import ContactSourceDb
from app.utils import errors as err
from app.utils.db.Condition import Order
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_contact

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.contact.model.CardAddressBook import CardAddressBook
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.source.ContactSource import ContactSource


class ContactSources:
    """Factory and lookup for ContactSource instances.

    Single entry point for all address book access - ModuleContact never touches
    RepositoryAddressBook directly. All reads are scoped to a user_uid.

    The optional user_source threaded through the read methods is the acting user's source config
    (a user belongs to exactly one source). When None, only the local DB address books are served;
    when provided, the directory/LDAP source is also surfaced - the seam for the annuaire, built
    with ContactSourceLdap later.
    """

    def __init__(self, db: ClientSQL) -> None:
        self._db = db
        self._repo_addressbook = RepositoryAddressBook(db)

    def get(self, addressbook: CardAddressBook, user_source: UserSourceSettingsObj | None = None) -> ContactSource:
        """Return the appropriate ContactSource for the given address book.

        Local books are served from the DB; user_source is reserved for building the directory/LDAP
        source (it carries the acting user's source config).
        """
        if addressbook.source_type == CardSourceType.LOCAL:
            return ContactSourceDb(self._db, addressbook)
        logger_contact.error("Unknown source_type=%s for address book key=%s", addressbook.source_type, addressbook.key)
        raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_SUPPORTED)

    def get_all(self, user_uid: str, user_source: UserSourceSettingsObj | None = None) -> list[ContactSource]:
        """Return a source for every address book owned by user_uid (local books; directory later)."""
        return [self.get(book, user_source) for book in self._repo_addressbook.find_all(user_uid)]

    def get_default(self, user_uid: str) -> ContactSource | None:
        """Return the default address book source for user_uid, or None if the user has none."""
        book: CardAddressBook | None = self._repo_addressbook.get_default_for_user(user_uid)
        return self.get(book) if book is not None else None

    def get_by_key(
        self, user_uid: str, key: str, user_source: UserSourceSettingsObj | None = None,
    ) -> ContactSource | None:
        """Return the source for a specific address book, or None if not found."""
        book = self._repo_addressbook.find_by_key(user_uid, key)
        return self.get(book, user_source) if book is not None else None

    def get_contacts(
        self, user_uid: str, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC, addressbook_key: str | None = None,
        user_source: UserSourceSettingsObj | None = None,
    ) -> tuple[list[CardContact], int]:
        """Return a page of contacts plus the total count.

        When addressbook_key is given, the query is scoped to that single address book (DB-level
        pagination). When None, contacts from every source of the user are merged, sorted by display
        name and paginated in memory - the seam through which the LDAP directory will also contribute.

        :param user_uid: Owner of the address books to query.
        :param search: Optional full-text query.
        :param offset: Number of contacts to skip (pagination).
        :param limit: Maximum number of contacts to return (0 = no limit).
        :param sort_by: Sort column applied at the DB level for the single-book case.
        :param order: Sort direction (ascending or descending).
        :param addressbook_key: Restrict to one book, or None to span all the user's books.
        :param user_source: Acting user's source config (None = local DB only).
        :return: A tuple (contacts page, total count matching the filter).
        """
        if addressbook_key is not None:
            source = self.get_by_key(user_uid, addressbook_key, user_source)
            if source is None:
                raise RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
            return source.get_contacts(search, offset, limit, sort_by, order), source.count_contacts(search)

        contacts: list[CardContact] = []
        for source in self.get_all(user_uid, user_source):
            contacts.extend(source.get_contacts(search))
        contacts.sort(key=lambda contact: (contact.display_name or "").casefold(), reverse=order == Order.DESC)
        total: int = len(contacts)
        page: list[CardContact] = contacts[offset:offset + limit] if limit else contacts[offset:]
        return page, total
