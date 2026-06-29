from __future__ import annotations

from typing import Any

from app.module.contact.model.CardUrl import CardUrl
from app.utils.serializer.Serializer import Serializer


class CardUrlSerializerDict(Serializer[CardUrl, dict[str, Any]]):
    """Serializes a CardUrl (vCard URL) to a dict."""

    def serialize(self, data: CardUrl) -> dict[str, Any]:
        """Convert a CardUrl to its dict representation."""
        return {"value": data.value, "type": data.type}
