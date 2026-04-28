from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.module.calendar.imip.ImipMethod import ImipMethod

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


@dataclass
class ImipMessage:
    """Represents an outgoing or incoming iMIP email message (RFC 6047).

    Used both for messages built by ImipBuilder (outgoing) and parsed by
    ImipParser (incoming from the agent's IMAP polling).
    """
    method: ImipMethod
    event: CalEvent
    from_email: str
    to_emails: list[str] = field(default_factory=list)
    ical_content: str = ""
