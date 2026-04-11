from __future__ import annotations

from dataclasses import dataclass, field

from app.module.calendar.model.enums.RelationType import RelationType


@dataclass
class CalEventRelation:
    """
    Relationship between a calendar event and another calendar component (RFC 5545 RELATED-TO).
    """
    uid: str
    relation_type: RelationType = field(default=RelationType.PARENT)
