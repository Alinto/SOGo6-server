from __future__ import annotations

from enum import Enum


class ComponentType(Enum):
    """
    Type of a calendar component (RFC 5545 §3.6).

    Maps to RFC 5545 component names in the iCal layer only:
      EVENT   ↔ VEVENT
      TASK    ↔ VTODO
      JOURNAL ↔ VJOURNAL
    """
    UNDEFINED = "undefined"
    EVENT   = "event"
    TASK    = "task"
    JOURNAL = "journal"
