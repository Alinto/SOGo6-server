from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.ContactsSerializer import ContactsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactAutocompleteSerializerList(ContactsSerializer[list]):
    """Flatten contacts to lightweight recipient suggestions: one {name, email} per email address.

    A contact with several emails yields several suggestions; a contact with none yields none
    (a recipient suggestion without an address is useless).
    """

    def serialize(self, data: list[CardContact]) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        for contact in data:
            address_book = (
                {"key": contact.addressbook_key, "name": contact.addressbook_name}
                if contact.addressbook_key else None
            )
            for email in contact.emails:
                suggestions.append({
                    "type": "contact",
                    "name": contact.display_name,
                    "email": email.value,
                    "contact_key": contact.key,
                    "list_key": None,
                    "member_count": None,
                    "members": None,
                    "address_book": address_book,
                })
        return suggestions
