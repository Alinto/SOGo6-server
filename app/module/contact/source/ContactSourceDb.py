from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.module.contact.repository.RepositoryAddressBook import RepositoryAddressBook
from app.module.contact.repository.RepositoryContact import RepositoryContact
from app.module.contact.repository.RepositoryContactList import RepositoryContactList
from app.module.contact.source.ContactSource import ContactSource
from app.utils.db.Condition import Order

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.contact.model.CardAddressBook import CardAddressBook
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList

# Relational columns a contact list may be ordered by. Guards the ORDER BY against arbitrary
# input reaching the SQL layer; an unknown sort_by falls back to display_name.
SORTABLE_COLUMNS: frozenset[str] = frozenset({
    tbl.COL_CT_DISPLAY_NAME.name, tbl.COL_CT_LAST_NAME.name, tbl.COL_CT_FIRST_NAME.name,
    tbl.COL_CT_ORGANIZATION.name, tbl.COL_CT_CREATED_AT.name, tbl.COL_CT_UPDATED_AT.name,
})

# Relational columns a distribution list may be ordered by; an unknown sort_by falls back to name.
LIST_SORTABLE_COLUMNS: frozenset[str] = frozenset({
    tbl.COL_LST_NAME.name, tbl.COL_LST_CREATED_AT.name, tbl.COL_LST_UPDATED_AT.name,
})


class ContactSourceDb(ContactSource):
    """Contact source backed by the local database (sogo_contacts_addressbooks + sogo_contacts_contacts)."""

    def __init__(self, db: ClientSQL, addressbook: CardAddressBook) -> None:
        super().__init__(addressbook)
        self._repo_addressbook = RepositoryAddressBook(db)
        self._repo_contact = RepositoryContact(db)
        self._repo_list = RepositoryContactList(db)

    def is_writable(self) -> bool:
        return True

    def save_addressbook(self, addressbook: CardAddressBook) -> CardAddressBook:
        """Insert a new address book row; clear other defaults when is_default=True."""
        self._addressbook = self._repo_addressbook.insert(addressbook)
        if self._addressbook.is_default:
            self._repo_addressbook.clear_default(self._addressbook.user_uid, self._addressbook.require_id)
        return self._addressbook

    def update_addressbook(self, addressbook: CardAddressBook) -> None:
        """Persist changes to the address book row; clear other defaults when is_default=True."""
        if addressbook.is_default:
            self._repo_addressbook.clear_default(addressbook.user_uid, addressbook.require_id)
        self._repo_addressbook.update(addressbook)
        self._addressbook = addressbook

    def delete_addressbook(self, hard_delete: bool = False) -> None:
        """Remove the book's lists then its contacts (tombstoned and detached by default, physical when hard), then the book row."""
        book_key: str = self._addressbook.require_key
        for card_list in self._repo_list.find_by_addressbook(book_key):
            self._repo_list.delete_members(card_list.require_key)
        self._repo_list.delete_all(book_key, hard_delete=hard_delete)
        self._repo_contact.delete_all(book_key, hard_delete=hard_delete)
        self._repo_addressbook.delete(self._addressbook.require_id)

    def get_contacts(
        self, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC,
    ) -> list[CardContact]:
        """Return non-deleted contacts of the book, paginated, sorted (display_name by default) and searched."""
        sort_column: str = sort_by if sort_by in SORTABLE_COLUMNS else tbl.COL_CT_DISPLAY_NAME.name
        return self._repo_contact.find_by_addressbook(
            self._addressbook.require_key, search, offset, limit, sort_column, order,
        )

    def count_contacts(self, search: str | None = None) -> int:
        """Return the number of non-deleted contacts matching the optional full-text filter."""
        return self._repo_contact.count_by_addressbook(self._addressbook.require_key, search)

    def get_contact_by_key(self, key: str) -> CardContact | None:
        """Return a contact by its opaque key within this book, or None."""
        return self._repo_contact.find_by_key(self._addressbook.require_key, key)

    def get_contact_by_uid(self, uid: str) -> CardContact | None:
        """Return a contact by its vCard UID within this book, or None."""
        return self._repo_contact.find_by_uid(self._addressbook.require_key, uid)

    def insert_contact(self, contact: CardContact) -> CardContact:
        """Persist a new contact and bump the book ctag."""
        created: CardContact = self._repo_contact.insert(contact)
        self._bump_ctag()
        return created

    def update_contact(self, contact: CardContact) -> None:
        """Persist changes to an existing contact and bump the book ctag."""
        self._repo_contact.update(contact)
        self._bump_ctag()

    def delete_contact(self, key: str) -> None:
        """Soft-delete a contact by key and bump the book ctag."""
        self._repo_contact.delete_by_key(self._addressbook.require_key, key)
        self._bump_ctag()

    def get_lists(
        self, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC,
    ) -> list[CardList]:
        """Return non-deleted lists of the book, paginated, sorted (name by default) and name-filtered; members populated."""
        sort_column: str = sort_by if sort_by in LIST_SORTABLE_COLUMNS else tbl.COL_LST_NAME.name
        lists: list[CardList] = self._repo_list.find_by_addressbook(
            self._addressbook.require_key, search, offset, limit, sort_column, order,
        )
        for card_list in lists:
            card_list.members = self._repo_list.find_member_keys(card_list.require_key)
        return lists

    def count_lists(self, search: str | None = None) -> int:
        """Return the number of non-deleted lists matching the optional name filter."""
        return self._repo_list.count_by_addressbook(self._addressbook.require_key, search)

    def get_list_by_key(self, key: str) -> CardList | None:
        """Return a list by its opaque key within this book with its members populated, or None."""
        card_list: CardList | None = self._repo_list.find_by_key(self._addressbook.require_key, key)
        if card_list is not None:
            card_list.members = self._repo_list.find_member_keys(card_list.require_key)
        return card_list

    def insert_list(self, card_list: CardList) -> CardList:
        """Persist a new list and its membership, bump the book ctag, and return it with members populated."""
        members: list[str] = card_list.members
        created: CardList = self._repo_list.insert(card_list)
        self._repo_list.replace_members(created.require_key, members)
        created.members = self._repo_list.find_member_keys(created.require_key)
        self._bump_ctag()
        return created

    def update_list(self, card_list: CardList) -> None:
        """Persist changes to an existing list and its membership, and bump the book ctag."""
        self._repo_list.update(card_list)
        self._repo_list.replace_members(card_list.require_key, card_list.members)
        self._bump_ctag()

    def delete_list(self, key: str) -> None:
        """Soft-delete a list by key, clear its membership, and bump the book ctag."""
        self._repo_list.delete_by_key(self._addressbook.require_key, key)
        self._repo_list.delete_members(key)
        self._bump_ctag()

    def _bump_ctag(self) -> None:
        """Increment the address book ctag so CardDAV clients detect the change (RFC 6352)."""
        self._addressbook.ctag = (self._addressbook.ctag or 0) + 1
        self._repo_addressbook.update(self._addressbook)
