from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalConferenceEntryPoint:
    """
    Single entry point (video, phone, etc.) for a conference call attached to an event.
    """
    type: str
    uri: str
    label: str | None = None
