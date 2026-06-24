from __future__ import annotations

from dataclasses import dataclass

from app.auth.User import User


@dataclass
class CalendarUser:
    """Carries both the acting user and the calendar owner for shared calendar operations.

    For personal calendars (no sharing), user and owner are the same object.
    The module uses owner.mail for organizer fields and owner.uid for calendar lookups.
    """

    user: User
    owner: User

    @classmethod
    def for_owner_uid(cls, user_uid: str | None) -> CalendarUser | None:
        """Build a self-acting CalendarUser for a calendar owner uid (acting user == owner).

        Used by the system reminder sweep, which has no request-bound acting user. Returns None
        when user_uid is empty.
        """
        if not user_uid:
            return None
        owner: User = User(uid=user_uid)
        return cls(user=owner, owner=owner)
