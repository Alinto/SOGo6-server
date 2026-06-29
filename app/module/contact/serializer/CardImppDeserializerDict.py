from __future__ import annotations

from typing import Any

from app.module.contact.model.CardImpp import CardImpp
from app.utils.serializer.Deserializer import Deserializer


class CardImppDeserializerDict(Deserializer[dict[str, Any], CardImpp]):
    """Deserializes a dict into a CardImpp (vCard IMPP)."""

    def deserialize(self, data: dict[str, Any]) -> CardImpp:
        """Convert a dict into a CardImpp."""
        return CardImpp(uri=data.get("uri", ""), type=data.get("type"))
