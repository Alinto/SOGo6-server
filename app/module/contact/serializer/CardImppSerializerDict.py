from __future__ import annotations

from typing import Any

from app.module.contact.model.CardImpp import CardImpp
from app.utils.serializer.Serializer import Serializer


class CardImppSerializerDict(Serializer[CardImpp, dict[str, Any]]):
    """Serializes a CardImpp (vCard IMPP) to a dict."""

    def serialize(self, data: CardImpp) -> dict[str, Any]:
        """Convert a CardImpp to its dict representation."""
        return {"uri": data.uri, "type": data.type}
