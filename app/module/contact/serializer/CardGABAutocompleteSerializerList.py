from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.GABContactsSerializer import GABContactsSerializer

class CardGABAutocompleteSerializerList(GABContactsSerializer[list]):
    """Flatten contacts to lightweight suggestions: one {name, email} per email address.

    A contact with several emails yields several suggestions; one without an email still yields a
    single name-only suggestion (email null), so a contact matched by name surfaces even with no
    address (the caller decides whether a no-address suggestion is selectable).
    """

    def serialize(self, data: list[dict]) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        for contact in data:
            address_book = {"key": contact["us_uid"], "name": contact["us_name"]}
                
            if len(contact["emails"]) > 1:
                suggestions.extend(self._suggestion(contact, email, address_book) for email in contact["emails"])
            else:
                suggestions.append(self._suggestion(contact, contact["emails"][0], address_book))
        return suggestions

    @staticmethod
    def _suggestion(contact: dict, email: str | None, address_book: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "type": "contact",
            "name": contact["name"],
            "email": email,
            "contact_key": contact["uid"],
            "list_key": None,
            "member_count": None,
            "members": None,
            "address_book": address_book,
        }
