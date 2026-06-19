from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.utils.serializer.Serializer import Serializer


class CalEventRelationSerializerDict(Serializer[CalEventRelation, dict[str, Any]]):
    """Serializes a CalEventRelation (RFC 5545 RELATED-TO) to a dict."""

    def serialize(self, data: CalEventRelation) -> dict[str, Any]:
        """Convert a CalEventRelation to its dict representation."""
        return {"uid": data.uid, "relation_type": data.relation_type.value}
