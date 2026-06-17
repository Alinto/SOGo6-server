from __future__ import annotations

from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class AddressBookContent(NamedTuple):
    """A book's exportable content: its contacts and its distribution lists."""

    contacts: list[CardContact]
    lists: list[CardList]
