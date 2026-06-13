from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.AddressBookSerializer import AddressBookSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardAddressBook import CardAddressBook


class AddressBookSerializerDict(AddressBookSerializer[dict]):
    """Converts a CardAddressBook to a plain dict matching the SOGo6 REST API schema."""

    def serialize(self, data: CardAddressBook) -> dict[str, Any]:
        return {
            "key": data.key,
            "name": data.name,
            "description": data.description,
            "is_default": data.is_default,
            "source_type": data.source_type.value,
            "ctag": data.ctag,
        }
