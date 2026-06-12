from __future__ import annotations

from enum import Enum


class CardKind(str, Enum):
    """Kind of object a card represents (vCard KIND, RFC 6350 §6.1.4)."""
    INDIVIDUAL = "individual"
    GROUP = "group"
    ORG = "org"
