from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardListsSerializer import CardListsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList


class CardListAutocompleteSerializerList(CardListsSerializer[list]):
    """Flatten distribution lists to recipient suggestions, one per list.

    A list surfaces in autocompletion as a full result carrying its member_count instead of an
    email address (a list expands to several recipients, it is not a single address). The shape
    matches the contact suggestion so a caller can render both from one list, discriminating on the
    type field.
    """

    def serialize(self, data: list[CardList]) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        for card_list in data:
            address_book = (
                {"key": card_list.addressbook_key, "name": card_list.addressbook_name}
                if card_list.addressbook_key else None
            )
            members = [
                {
                    "contact_key": contact.key,
                    "name": contact.display_name,
                    "email": contact.emails[0].value if contact.emails else None,
                }
                for contact in card_list.member_contacts
            ]
            suggestions.append({
                "type": "list",
                "name": card_list.name,
                "email": None,
                "contact_key": None,
                "list_key": card_list.key,
                "member_count": len(members),
                "members": members,
                "address_book": address_book,
            })
        return suggestions
