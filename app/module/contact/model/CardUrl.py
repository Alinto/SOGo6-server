from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CardUrl:
    """Web address associated with a contact (vCard URL, RFC 6350 §6.7.8)."""
    # The URL itself
    value: str
    # Single TYPE parameter value (e.g. "home", "work"); None when unspecified. A multi-valued TYPE
    # (RFC 6350 allows "TYPE=work,home") is not preserved here, unlike CardEmail/CardPhone/CardAddress.
    type: str | None = None
