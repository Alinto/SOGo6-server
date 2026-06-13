from __future__ import annotations

from typing import Any

from app.module.contact.model.CardPhone import CardPhone
from app.utils.serializer.Serializer import Serializer


class CardPhoneSerializerDict(Serializer[CardPhone, dict[str, Any]]):
    """Serializes a CardPhone (vCard TEL) to a dict."""

    def serialize(self, data: CardPhone) -> dict[str, Any]:
        """Convert a CardPhone to its dict representation."""
        return {"number": data.number, "types": data.types, "pref": data.pref}
