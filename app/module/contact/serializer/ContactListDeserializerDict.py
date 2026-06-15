from __future__ import annotations

import dataclasses
from typing import Any

from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.ContactListDeserializer import ContactListDeserializer


class ContactListDeserializerDict(ContactListDeserializer[dict]):
    """Deserializes plain dicts into CardList objects.

    Fields absent from the dict keep the CardList dataclass default. Identity fields (key, uid,
    addressbook_key) are accepted but re-asserted by ModuleContact on write; members is the list of
    member contact keys.
    """

    def deserialize(self, data: dict[str, Any]) -> CardList:
        """Convert a dict into a CardList."""
        return CardList(
            key=data.get("key"),
            addressbook_key=data.get("addressbook_key"),
            uid=data.get("uid"),
            name=data["name"],
            description=data.get("description"),
            members=list(data.get("members", [])),
        )

    def deserialize_with_update(self, origin: CardList, update: dict | CardList) -> CardList:
        """Apply a partial update to an existing CardList and return the result.

        When update is a dict, only keys present in CardList.MUTABLE_FIELDS (name, description,
        members) are applied to a copy of origin; identity fields are ignored here and re-asserted by
        ModuleContact.update_list. When update is a CardList, return it directly.
        """
        if isinstance(update, CardList):
            return update

        merged: CardList = dataclasses.replace(origin)
        for key, value in update.items():
            if key in CardList.MUTABLE_FIELDS:
                setattr(merged, key, list(value) if key == "members" else value)
        return merged
