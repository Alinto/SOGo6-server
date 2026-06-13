from __future__ import annotations

from typing import Any

from app.module.contact.model.CardAddress import CardAddress
from app.utils.serializer.Deserializer import Deserializer


class CardAddressDeserializerDict(Deserializer[dict[str, Any], CardAddress]):
    """Deserializes a dict into a CardAddress (vCard ADR)."""

    def deserialize(self, data: dict[str, Any]) -> CardAddress:
        """Convert a dict into a CardAddress."""
        return CardAddress(
            po_box=data.get("po_box"),
            extended=data.get("extended"),
            street=data.get("street"),
            locality=data.get("locality"),
            region=data.get("region"),
            postal_code=data.get("postal_code"),
            country=data.get("country"),
            types=data.get("types", []),
            pref=data.get("pref"),
        )
