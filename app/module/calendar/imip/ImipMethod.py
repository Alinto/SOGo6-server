from __future__ import annotations

from enum import Enum


class ImipMethod(str, Enum):
    """iTIP method values used in iMIP email delivery (RFC 5546 §1.4)."""
    REQUEST = "REQUEST"
    REPLY = "REPLY"
    CANCEL = "CANCEL"
