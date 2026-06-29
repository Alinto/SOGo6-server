from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, TYPE_CHECKING

from app.utils.exceptions import BugException

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


@dataclass
class CardList:  # pylint: disable=too-many-instance-attributes
    """Format-agnostic representation of a distribution list (vCard KIND:group, RFC 6350 §6.1.4).

    A list belongs to one address book and groups member contacts by reference: members are
    contact keys held in the sogo6_contacts_list_members join table, not embedded data, so editing
    a member contact propagates to every list it belongs to. Maps to sogo6_contacts_lists.

    Members are restricted to contacts of the list's own address book (enforced by the service
    layer). A foreign MEMBER URI that RFC 6350 6.6.5 allows but that does not resolve to a contact
    of this book (e.g. "mailto:" or a contact from another book) cannot be represented and would be
    dropped when importing a third-party KIND:group card.

    id is the internal integer PK; key is the opaque public identifier exposed in the API (prevents
    row enumeration). uid is the vCard UID, dormant while the API is REST only and used by the
    KIND:group serializer.
    """
    # FN (RFC 6350 §6.2.1) - the list display name
    name: str

    # Internal - database auto-increment PK
    id: int | None = None
    # Internal - opaque token exposed in the API
    key: str | None = None
    # Key of the owning address book (sogo6_contacts_addressbooks.key)
    addressbook_key: str | None = None
    # vCard UID (RFC 6350 §6.7.6) - stable identity carried in the .vcf, dormant until the KIND:group serializer
    uid: str | None = None
    # NOTE (RFC 6350 §6.7.2) - the conventional carrier for a free-text list description
    description: str | None = None
    # MEMBER (RFC 6350 §6.6.5) - member contact keys (references into sogo6_contacts_contacts.key),
    # valid only on a KIND:group card; loaded from the join table
    members: list[str] = field(default_factory=list)
    # Transient - originating address book name, stamped at fetch time for display (autocomplete
    # provenance), never persisted; mirrors CardContact.addressbook_name
    addressbook_name: str | None = None
    # Transient - members resolved to their CardContact, populated for autocomplete only (so a list
    # suggestion can carry each member's name and email); never persisted
    member_contacts: list[CardContact] = field(default_factory=list)

    is_deleted: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    _MUTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"name", "description", "members"})

    @staticmethod
    def is_mutable_field(field_name: str) -> bool:
        """Return True if the field accepts partial updates."""
        return field_name in CardList._MUTABLE_FIELDS

    @property
    def require_id(self) -> int:
        """Internal PK, guaranteed once the list has been persisted/loaded."""
        if self.id is None:
            raise BugException("CardList.id accessed before the list was persisted")
        return self.id

    @property
    def require_key(self) -> str:
        """Opaque public key, guaranteed once the list has been persisted/loaded."""
        if self.key is None:
            raise BugException("CardList.key accessed before the list was persisted")
        return self.key

    @property
    def require_addressbook_key(self) -> str:
        """Owning address book key, guaranteed once the list is attached to a book."""
        if self.addressbook_key is None:
            raise BugException("CardList.addressbook_key accessed before it was set")
        return self.addressbook_key

    def apply_update(self, updates: dict[str, Any]) -> None:
        """Apply a partial update dict to this list, ignoring unknown or immutable fields."""
        for field_name, value in updates.items():
            if field_name in self._MUTABLE_FIELDS:
                setattr(self, field_name, value)
