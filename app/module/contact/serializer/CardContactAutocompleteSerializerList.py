from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardContactsSerializer import CardContactsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class CardContactAutocompleteSerializerList(CardContactsSerializer[list]):
    """Flatten contacts to lightweight suggestions: one {name, email} per email address.

    A contact with several emails yields several suggestions; one without an email still yields a
    single name-only suggestion (email null), so a contact matched by name surfaces even with no
    address (the caller decides whether a no-address suggestion is selectable).
    """

    def serialize(self, data: list[CardContact]) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        for contact in data:
            address_book = (
                {"key": contact.addressbook_key, "name": contact.addressbook_name}
                if contact.addressbook_key else None
            )
            if contact.emails:
                suggestions.extend(self._suggestion(contact, email.value, address_book) for email in contact.emails)
            else:
                suggestions.append(self._suggestion(contact, None, address_book))
        return suggestions

    @staticmethod
    def _suggestion(contact: CardContact, email: str | None, address_book: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "type": "contact",
            "name": contact.display_name,
            "email": email,
            "contact_key": contact.key,
            "list_key": None,
            "member_count": None,
            "members": None,
            "address_book": address_book,
        }
