from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CardImpp:
    """Instant messaging and presence URI of a contact (vCard IMPP, RFC 6350 §6.4.3)."""
    # The IM URI (e.g. "xmpp:alice@example.com", "sip:bob@example.com")
    uri: str
    # TYPE parameter value (e.g. "home", "work"); None when unspecified
    type: str | None = None
