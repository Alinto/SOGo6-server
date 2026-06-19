from __future__ import annotations

from typing import Any

from app.module.contact.model.CardPhone import CardPhone
from app.utils.serializer.Deserializer import Deserializer


class CardPhoneDeserializerDict(Deserializer[dict[str, Any], CardPhone]):
    """Deserializes a dict into a CardPhone (vCard TEL)."""

    def deserialize(self, data: dict[str, Any]) -> CardPhone:
        """Convert a dict into a CardPhone."""
        return CardPhone(number=data.get("number", ""), types=data.get("types", []), pref=data.get("pref"))
