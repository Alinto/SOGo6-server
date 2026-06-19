from __future__ import annotations

from dataclasses import dataclass, field

from app.module.calendar.model.enums.RelationType import RelationType


@dataclass
class CalEventRelation:
    """
    Directed relationship from one calendar component to another (RFC 5545 §3.8.4.5 RELATED-TO).
    """
    # RFC 5545 §3.8.4.7 UID - the UID of the related component
    uid: str
    # RFC 5545 §3.2.15 RELTYPE parameter - nature of the relationship
    relation_type: RelationType = field(default=RelationType.PARENT)
