from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardContactSerializerDict import CardContactSerializerDict
from app.module.contact.serializer.CardContactsSerializer import CardContactsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class CardContactsSerializerList(CardContactsSerializer[list]):
    """Converts a list of CardContact objects to a list of dicts."""

    def __init__(self, contact_serializer: CardContactSerializerDict | None = None) -> None:
        self._contact_serializer: CardContactSerializerDict = contact_serializer or CardContactSerializerDict()

    def serialize(self, data: list[CardContact]) -> list[dict[str, Any]]:
        return [self._contact_serializer.serialize(contact) for contact in data]
