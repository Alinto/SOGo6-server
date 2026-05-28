from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.CalendarShareLevel import CalendarShareLevel
from app.module.calendar.model.enums.EventVisibility import EventVisibility


@dataclass
class CalendarPermissions:
    """Permission set for a user on a specific calendar, per visibility class.

    Each visibility class (public, confidential, private) has an independent
    share level. can_create and can_delete are calendar-wide flags.
    """

    public_level: CalendarShareLevel
    confidential_level: CalendarShareLevel
    private_level: CalendarShareLevel
    can_create: bool
    can_delete: bool

    @staticmethod
    def owner() -> CalendarPermissions:
        """Full permissions for the calendar owner."""
        return CalendarPermissions(
            public_level=CalendarShareLevel.MODIFY,
            confidential_level=CalendarShareLevel.MODIFY,
            private_level=CalendarShareLevel.MODIFY,
            can_create=True,
            can_delete=True,
        )

    @staticmethod
    def denied() -> CalendarPermissions:
        """No permissions at all."""
        return CalendarPermissions(
            public_level=CalendarShareLevel.NONE,
            confidential_level=CalendarShareLevel.NONE,
            private_level=CalendarShareLevel.NONE,
            can_create=False,
            can_delete=False,
        )

    def level_for_visibility(self, visibility: EventVisibility) -> CalendarShareLevel:
        """Return the share level for the given event visibility class."""
        if visibility == EventVisibility.CONFIDENTIAL:
            return self.confidential_level
        if visibility == EventVisibility.PRIVATE:
            return self.private_level
        return self.public_level
