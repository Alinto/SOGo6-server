from __future__ import annotations

from typing import Any

from app.module.contact.model.CardUrl import CardUrl
from app.utils.serializer.Deserializer import Deserializer


class CardUrlDeserializerDict(Deserializer[dict[str, Any], CardUrl]):
    """Deserializes a dict into a CardUrl (vCard URL)."""

    def deserialize(self, data: dict[str, Any]) -> CardUrl:
        """Convert a dict into a CardUrl."""
        return CardUrl(value=data.get("value", ""), type=data.get("type"))
