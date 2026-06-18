from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalConferenceEntryPoint:
    """
    Single dial-in entry point for a conference call (Google Calendar API - no RFC basis).

    Common types: "video", "phone", "sip", "more".
    """
    # Entry point type, e.g. "video", "phone"
    type: str
    # Dial-in URI - https:// for video, tel: for phone, sip: for SIP
    uri: str
    # Human-readable label shown in the UI
    label: str | None = None
