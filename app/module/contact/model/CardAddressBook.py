from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.utils.exceptions import BugException


@dataclass
class CardAddressBook:  # pylint: disable=too-many-instance-attributes
    """Format-agnostic representation of an address book (RFC 6352 addressbook collection).

    The address book is the top-level container and the unit of sharing: a contact belongs to
    exactly one book. Maps to sogo_contacts_addressbooks. id is the internal integer PK; key is
    the opaque public identifier exposed in the API (prevents row enumeration).

    source_type drives the source dispatch: 'local' (DB-backed, full CRUD) or 'carddav'
    (read-write sync with a remote server). External sync metadata lives in sync_config JSON.
    """
    # Internal - owner's uid, FK to sogo_user_profiles.uid
    user_uid: str
    # Display name of the address book
    name: str

    # Internal - database auto-increment PK
    id: int | None = None
    # Internal - opaque token exposed in the API
    key: str | None = None
    # Free-text description
    description: str | None = None
    # Internal - marks the user's primary address book; uniqueness enforced by the service layer
    is_default: bool = False
    # Internal - discriminates the backend: local, carddav
    source_type: CardSourceType = CardSourceType.UNDEFINED
    # CardDAV CS:getctag (RFC 6352) - opaque token bumped by the service layer on every contact
    # mutation so clients detect changes without fetching the full contact list.
    ctag: int = 0
    # External CardDAV sync metadata (url, username, password, etag, last_sync); NULL for local books.
    sync_config: dict | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    MUTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"name", "description", "is_default", "sync_config"})

    @property
    def require_id(self) -> int:
        """Internal PK, guaranteed once the address book has been persisted/loaded."""
        if self.id is None:
            raise BugException("CardAddressBook.id accessed before the address book was persisted")
        return self.id

    @property
    def require_key(self) -> str:
        """Opaque public key, guaranteed once the address book has been persisted/loaded."""
        if self.key is None:
            raise BugException("CardAddressBook.key accessed before the address book was persisted")
        return self.key

    def apply_update(self, updates: dict[str, Any]) -> None:
        """Apply a partial update dict to this address book, ignoring unknown or immutable fields."""
        for field_name, value in updates.items():
            if field_name in self.MUTABLE_FIELDS:
                setattr(self, field_name, value)
