from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.enums.RelationType import RelationType
from app.utils.serializer.Deserializer import Deserializer


class CalEventRelationDeserializerDict(Deserializer[dict[str, Any], CalEventRelation]):
    """Deserializes a dict into a CalEventRelation (RFC 5545 RELATED-TO)."""

    def deserialize(self, data: dict[str, Any]) -> CalEventRelation:
        """Convert a dict into a CalEventRelation."""
        return CalEventRelation(
            uid=data.get("uid", ""),
            relation_type=RelationType(data["relation_type"]) if "relation_type" in data else RelationType.PARENT,
        )
