from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CardUrl:
    """Web address associated with a contact (vCard URL, RFC 6350 §6.7.8)."""
    # The URL itself
    value: str
    # TYPE parameter value (e.g. "home", "work"); None when unspecified
    type: str | None = None
