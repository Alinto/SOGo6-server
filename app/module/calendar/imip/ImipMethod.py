from __future__ import annotations

from enum import Enum


class ImipMethod(str, Enum):
    """iTIP method values used in iMIP email delivery (RFC 5546 §3.2)."""
    REQUEST = "REQUEST"
    REPLY = "REPLY"
    CANCEL = "CANCEL"
