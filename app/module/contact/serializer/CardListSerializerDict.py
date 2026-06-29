from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardListSerializer import CardListSerializer
from app.utils.datetime.DateTimeUtils import fmt_dt

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList


class CardListSerializerDict(CardListSerializer[dict]):
    """Converts a CardList to its plain dict representation.

    Members are exposed as the list of member contact keys (references), with member_count for a
    cheap size readout; resolving each member to a full contact is the caller's concern. Timestamps
    are ISO 8601 UTC.
    """

    def serialize(self, data: CardList) -> dict[str, Any]:
        return {
            "key": data.key,
            "uid": data.uid,
            "name": data.name,
            "description": data.description,
            "members": list(data.members),
            "member_count": len(data.members),
            "created_at": fmt_dt(data.created_at) if data.created_at else None,
            "updated_at": fmt_dt(data.updated_at) if data.updated_at else None,
        }
