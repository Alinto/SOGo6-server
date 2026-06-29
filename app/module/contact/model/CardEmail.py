from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CardEmail:
    """Email address of a contact (vCard EMAIL, RFC 6350 §6.4.2)."""
    # The email address itself
    value: str
    # TYPE parameter values (e.g. "home", "work")
    types: list[str] = field(default_factory=list)
    # PREF parameter (1-100, lower is preferred); None when unspecified
    pref: int | None = None
