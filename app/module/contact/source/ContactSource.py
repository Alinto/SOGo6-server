from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.utils.db.Condition import Order

if TYPE_CHECKING:
    from app.module.contact.model.CardAddressBook import CardAddressBook
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class ContactSource(ABC):
    """Abstract base class for a contact source (an address book backend).

    Subclasses implement the persistence operations. The local DB source is the only backend
    for now; a CardDAV mirror will plug in here later (RFC 6352).
    """

    def __init__(self, addressbook: CardAddressBook) -> None:
        """Initialise the source with its associated address book."""
        self._addressbook = addressbook

    @property
    def addressbook(self) -> CardAddressBook:
        """The address book associated with this source."""
        return self._addressbook

    @abstractmethod
    def is_writable(self) -> bool:
        """Whether contacts can be created, updated or deleted on this source."""

    @abstractmethod
    def save_addressbook(self, addressbook: CardAddressBook) -> CardAddressBook:
        """Persist a new address book and return it with id and key populated."""

    @abstractmethod
    def update_addressbook(self, addressbook: CardAddressBook) -> None:
        """Persist changes to the address book row."""

    @abstractmethod
    def delete_addressbook(self, hard_delete: bool = False) -> None:
        """Delete the address book; its contacts are tombstoned (soft) or physically removed (hard)."""

    @abstractmethod
    def get_contacts(
        self, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC,
    ) -> list[CardContact]:
        """Return the address book's contacts, paginated, sorted and optionally full-text filtered."""

    @abstractmethod
    def count_contacts(self, search: str | None = None) -> int:
        """Return the number of contacts matching the optional full-text filter (for pagination)."""

    @abstractmethod
    def get_contact_by_key(self, key: str) -> CardContact | None:
        """Return a contact by its opaque key, or None."""

    @abstractmethod
    def get_contact_by_uid(self, uid: str) -> CardContact | None:
        """Return a contact by its vCard UID, or None."""

    @abstractmethod
    def insert_contact(self, contact: CardContact) -> CardContact:
        """Persist a new contact and return it with id and key populated."""

    @abstractmethod
    def update_contact(self, contact: CardContact) -> None:
        """Persist changes to an existing contact."""

    @abstractmethod
    def delete_contact(self, key: str) -> None:
        """Soft-delete a contact by its opaque key."""

    @abstractmethod
    def get_lists(
        self, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC,
    ) -> list[CardList]:
        """Return the book's distribution lists, paginated, sorted and optionally name-filtered (members populated)."""

    @abstractmethod
    def count_lists(self, search: str | None = None) -> int:
        """Return the number of distribution lists matching the optional name filter (for pagination)."""

    @abstractmethod
    def get_list_by_key(self, key: str) -> CardList | None:
        """Return a distribution list by its opaque key with its members populated, or None."""

    @abstractmethod
    def insert_list(self, card_list: CardList) -> CardList:
        """Persist a new distribution list and its membership, and return it with id and key populated."""

    @abstractmethod
    def update_list(self, card_list: CardList) -> None:
        """Persist changes to an existing distribution list and its membership."""

    @abstractmethod
    def delete_list(self, key: str) -> None:
        """Soft-delete a distribution list by its opaque key and clear its membership."""
