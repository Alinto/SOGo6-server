from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.source.ContactSource import ContactSource
from app.utils.db.Condition import Order

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj
    from app.module.contact.model.CardAddressBook import CardAddressBook
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class ContactSourceDirectory(ContactSource):  # pylint: disable=unused-argument
    """Contact source backed by a domain user source (the directory / annuaire), SQL or LDAP.

    Surfaces the domain directory as a synthetic, domain-wide address book so its entries
    contribute to transverse search and recipient autocompletion alongside the user's personal
    contacts. The backend is abstracted by the user source layer (US_TYPE = sql | ldap); this class
    is only an adapter that maps directory entries to CardContact. Mirrors SOGo's
    SOGoContactSourceFolder (a system source with isAddressBook), not an ACL-shared personal book.

    TODO: not implemented yet. Open work before this is functional:
      - add a CardSourceType.DIRECTORY value and dispatch to it in ContactSources.get/get_all
        (surfaced as a domain-wide source when the user source declares US_IS_ADDRESSBOOK)
      - build the synthetic CardAddressBook representing the directory
      - adapt the user source query primitive (owned by ModuleUserSource, which dispatches SQL vs
        LDAP) and map each directory entry to a CardContact
      - apply US_AUTO_QUERY_LIMIT and require a search term for large directories instead of the
        in-memory merge used for local books
      - derive is_writable from the backend (LDAP is read-only; a SQL system source may be writable
        by configured modifiers, like SOGo's [source modifiers])
    """

    def __init__(self, addressbook: CardAddressBook, user_source: UserSourceSettingsObj) -> None:
        super().__init__(addressbook)
        # TODO: keep the acting user's source config and build/inject the directory query client.
        self._user_source = user_source

    def is_writable(self) -> bool:
        # TODO: derive from the backend (LDAP read-only; SQL system source writable by modifiers).
        # Read-only is the safe default until the directory write path is designed.
        return False

    def save_addressbook(self, addressbook: CardAddressBook) -> CardAddressBook:
        raise NotImplementedError("TODO: the directory address book is synthetic")

    def update_addressbook(self, addressbook: CardAddressBook) -> None:
        raise NotImplementedError("TODO: the directory address book is synthetic")

    def delete_addressbook(self, hard_delete: bool = False) -> None:
        raise NotImplementedError("TODO: the directory address book is synthetic")

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
        # TODO: resolve a directory entry by its opaque key (mapped from the backend dn/uid).
        raise NotImplementedError("TODO: directory contact lookup not implemented")

    def get_contact_by_uid(self, uid: str) -> CardContact | None:
        raise NotImplementedError("TODO: directory contact lookup not implemented")

    def insert_contact(self, contact: CardContact) -> CardContact:
        raise NotImplementedError("TODO: directory write path not designed yet")

    def update_contact(self, contact: CardContact) -> None:
        raise NotImplementedError("TODO: directory write path not designed yet")

    def delete_contact(self, key: str) -> None:
        raise NotImplementedError("TODO: directory write path not designed yet")

    def get_lists(
        self, search: str | None = None, offset: int = 0, limit: int = 0,
        sort_by: str | None = None, order: Order = Order.ASC,
    ) -> list[CardList]:
        # A directory has no distribution lists; lists are a local-book concept only.
        raise NotImplementedError("TODO: the directory has no distribution lists")

    def count_lists(self, search: str | None = None) -> int:
        raise NotImplementedError("TODO: the directory has no distribution lists")

    def get_list_by_key(self, key: str) -> CardList | None:
        raise NotImplementedError("TODO: the directory has no distribution lists")

    def get_list_by_uid(self, uid: str) -> CardList | None:
        raise NotImplementedError("TODO: the directory has no distribution lists")

    def insert_list(self, card_list: CardList) -> CardList:
        raise NotImplementedError("TODO: the directory has no distribution lists")

    def update_list(self, card_list: CardList) -> None:
        raise NotImplementedError("TODO: the directory has no distribution lists")

    def delete_list(self, key: str) -> None:
        raise NotImplementedError("TODO: the directory has no distribution lists")
