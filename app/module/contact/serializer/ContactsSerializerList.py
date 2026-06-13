from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.ContactSerializerDict import ContactSerializerDict
from app.module.contact.serializer.ContactsSerializer import ContactsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactsSerializerList(ContactsSerializer[list]):
    """Converts a list of CardContact objects to a list of dicts."""

    def __init__(self, contact_serializer: ContactSerializerDict | None = None) -> None:
        self._contact_serializer: ContactSerializerDict = contact_serializer or ContactSerializerDict()

    def serialize(self, data: list[CardContact]) -> list[dict[str, Any]]:
        return [self._contact_serializer.serialize(contact) for contact in data]
