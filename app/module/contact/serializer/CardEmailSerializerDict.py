from __future__ import annotations

from typing import Any

from app.module.contact.model.CardEmail import CardEmail
from app.utils.serializer.Serializer import Serializer


class CardEmailSerializerDict(Serializer[CardEmail, dict[str, Any]]):
    """Serializes a CardEmail (vCard EMAIL) to a dict."""

    def serialize(self, data: CardEmail) -> dict[str, Any]:
        """Convert a CardEmail to its dict representation."""
        return {"value": data.value, "types": data.types, "pref": data.pref}
