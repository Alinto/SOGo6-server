from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardAddressBookSerializer import CardAddressBookSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardAddressBook import CardAddressBook


class CardAddressBookSerializerDict(CardAddressBookSerializer[dict]):
    """Converts a CardAddressBook to its plain dict representation."""

    def serialize(self, data: CardAddressBook) -> dict[str, Any]:
        return {
            "key": data.key,
            "name": data.name,
            "description": data.description,
            "is_default": data.is_default,
            "source_type": data.source_type.value,
            "ctag": data.ctag,
        }
