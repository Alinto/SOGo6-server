from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CardPhone:
    """Telephone number of a contact (vCard TEL, RFC 6350 §6.4.1)."""
    # The phone number (free-form text per RFC 6350)
    number: str
    # TYPE parameter values (e.g. "voice", "cell", "fax", "home", "work")
    types: list[str] = field(default_factory=list)
    # PREF parameter (1-100, lower is preferred); None when unspecified
    pref: int | None = None
