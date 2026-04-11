from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CalCalendar:  # pylint: disable=too-many-instance-attributes
    """
    Format-agnostic representation of a calendar (personal agenda).

    Maps to the sogo_calendars table. The id field is the internal integer PK;
    hash is the opaque public identifier exposed in the API.

    iCalendar-level properties (prodid, calscale, method) are populated when
    the object is built from a VCALENDAR source (ICS / CalDAV).
    Unknown or vendor-specific properties (X-WR-*, X-APPLE-*, etc.) are
    collected in extra_properties.
    """

    owner_uid: str
    name: str

    id: int | None = None
    hash: str | None = None
    color: str | None = None
    description: str | None = None
    timezone: str = "UTC"
    is_default: bool = False
    subscription_token: str | None = None

    # iCalendar VCALENDAR-level properties
    prodid: str | None = None
    calscale: str | None = None
    method: str | None = None

    # Vendor / unknown X-* properties (e.g. X-WR-CALNAME, X-WR-CALDESC)
    extra_properties: dict[str, str] = field(default_factory=dict)

    created_at: datetime | None = None
    updated_at: datetime | None = None
