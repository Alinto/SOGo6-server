from __future__ import annotations

from typing import Any

from app.module.contact.model.CardAddress import CardAddress
from app.utils.serializer.Serializer import Serializer


class CardAddressSerializerDict(Serializer[CardAddress, dict[str, Any]]):
    """Serializes a CardAddress (vCard ADR) to a dict."""

    def serialize(self, data: CardAddress) -> dict[str, Any]:
        """Convert a CardAddress to its dict representation."""
        return {
            "po_box": data.po_box,
            "extended": data.extended,
            "street": data.street,
            "locality": data.locality,
            "region": data.region,
            "postal_code": data.postal_code,
            "country": data.country,
            "types": data.types,
            "pref": data.pref,
        }
