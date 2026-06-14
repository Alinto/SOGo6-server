from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.source.ContactSource import ContactSource
from app.utils.db.Condition import Order

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj
    from app.module.contact.model.CardAddressBook import CardAddressBook
    from app.module.contact.model.CardContact import CardContact


class ContactSourceLdap(ContactSource):  # pylint: disable=unused-argument
    """Read-only contact source backed by an LDAP/SQL directory (the annuaire).

    Surfaces the domain user directory as a synthetic, read-only address book so directory
    entries contribute to transverse search and recipient autocompletion alongside the user's
    personal contacts. Entries are queried through the user source layer (UserSourceSettingsObj:
    US_SEARCH, US_AUTO_QUERY_LIMIT, US_HIDDEN_USER...) and mapped to CardContact.

    TODO: not implemented yet. Open work before this is functional:
      - add a CardSourceType.DIRECTORY value and dispatch to it in ContactSources.get/get_all
      - build the synthetic read-only CardAddressBook representing the directory
      - adapt the directory query primitive (owned by the user source / annuaire layer) and map
        each directory entry to a CardContact
      - apply US_AUTO_QUERY_LIMIT and require a search term for large directories instead of the
        in-memory merge used for local books
    """

    def __init__(self, addressbook: CardAddressBook, user_source: UserSourceSettingsObj) -> None:
        super().__init__(addressbook)
        # TODO: keep the acting user's source config and build/inject the directory query client.
        self._user_source = user_source

    def is_writable(self) -> bool:
        # A directory is read-only: contacts cannot be created, updated or deleted through it.
        return False

    def save_addressbook(self, addressbook: CardAddressBook) -> CardAddressBook:
        raise NotImplementedError("TODO: the directory address book is synthetic and read-only")

    def update_addressbook(self, addressbook: CardAddressBook) -> None:
        raise NotImplementedError("TODO: the directory address book is synthetic and read-only")

    def delete_addressbook(self, hard_delete: bool = False) -> None:
        raise NotImplementedError("TODO: the directory address book is synthetic and read-only")

    def get_contacts(
        self, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC,
    ) -> list[CardContact]:
        # TODO: query the directory (apply US_AUTO_QUERY_LIMIT; require a search term for large
        # directories) and map each entry to a CardContact.
        raise NotImplementedError("TODO: directory contact search not implemented")

    def count_contacts(self, search: str | None = None) -> int:
        raise NotImplementedError("TODO: directory contact count not implemented")

    def get_contact_by_key(self, key: str) -> CardContact | None:
        # TODO: resolve a directory entry by its opaque key (mapped from the LDAP dn/uid).
        raise NotImplementedError("TODO: directory contact lookup not implemented")

    def get_contact_by_uid(self, uid: str) -> CardContact | None:
        raise NotImplementedError("TODO: directory contact lookup not implemented")

    def insert_contact(self, contact: CardContact) -> CardContact:
        raise NotImplementedError("TODO: the directory address book is synthetic and read-only")

    def update_contact(self, contact: CardContact) -> None:
        raise NotImplementedError("TODO: the directory address book is synthetic and read-only")

    def delete_contact(self, key: str) -> None:
        raise NotImplementedError("TODO: the directory address book is synthetic and read-only")
