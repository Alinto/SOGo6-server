from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.auth.User import User


@dataclass
class CalendarUser:
    """Carries both the acting user and the calendar owner for shared calendar operations.

    For personal calendars (no sharing), user and owner are the same object.
    The module uses owner.mail for organizer fields and owner.uid for calendar lookups.
    """

    user: User
    owner: User
