from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardListSerializerDict import CardListSerializerDict
from app.module.contact.serializer.CardListsSerializer import CardListsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList


class CardListsSerializerList(CardListsSerializer[list]):
    """Converts a list of CardList objects to a list of dicts."""

    def __init__(self, list_serializer: CardListSerializerDict | None = None) -> None:
        self._list_serializer: CardListSerializerDict = list_serializer or CardListSerializerDict()

    def serialize(self, data: list[CardList]) -> list[dict[str, Any]]:
        return [self._list_serializer.serialize(card_list) for card_list in data]
