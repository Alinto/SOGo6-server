from __future__ import annotations

from enum import Enum


class RelationType(Enum):
    """
    Type of relationship between two calendar components (RFC 5545 RELTYPE).
    """
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
