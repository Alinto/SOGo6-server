from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CardImpp:
    """Instant messaging and presence URI of a contact (vCard IMPP, RFC 6350 §6.4.3)."""
    # The IM URI (e.g. "xmpp:alice@example.com", "sip:bob@example.com")
    uri: str
    # Single TYPE parameter value (e.g. "home", "work"); None when unspecified. A multi-valued TYPE
    # (RFC 6350 allows "TYPE=work,home") is not preserved here, unlike CardEmail/CardPhone/CardAddress.
    type: str | None = None
