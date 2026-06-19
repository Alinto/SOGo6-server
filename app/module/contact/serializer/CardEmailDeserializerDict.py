from __future__ import annotations

from typing import Any

from app.module.contact.model.CardEmail import CardEmail
from app.utils.serializer.Deserializer import Deserializer


class CardEmailDeserializerDict(Deserializer[dict[str, Any], CardEmail]):
    """Deserializes a dict into a CardEmail (vCard EMAIL)."""

    def deserialize(self, data: dict[str, Any]) -> CardEmail:
        """Convert a dict into a CardEmail."""
        return CardEmail(value=data.get("value", ""), types=data.get("types", []), pref=data.get("pref"))
