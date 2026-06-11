from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.model.enums.CalendarPermissionAction import CalendarPermissionAction
from app.module.calendar.model.enums.CalendarShareLevel import CalendarShareLevel
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.utils import errors as err
from app.utils.exceptions import BugException, RequestException

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.CalendarUser import CalendarUser

_BUSY_TITLE = "Busy"


class CalendarAclEngine:
    """Resolves and enforces calendar permissions.

    Centralizes all ACL logic: permission resolution, action checks, and event sanitization.
    Currently stubbed — owner gets full access, non-owner is denied.
    Will be connected to the ACL module when it is implemented.
    """

    def get_permissions(self, calendar: CalCalendar, calendar_user: CalendarUser) -> CalendarPermissions:
        """Resolve the permissions for a user on a specific calendar.

        Owner gets full access on local calendars. Non-owner is denied (stub).
        ICS calendars can be shared with overridden permissions, but events are never
        writable: levels are capped at VIEW_ALL and create/modify are always denied.
        """
        is_owner: bool = calendar_user.user.uid == calendar_user.owner.uid
        if calendar.source_type == CalendarSourceType.ICS:
            if is_owner:
                base: CalendarPermissions = CalendarPermissions(
                    public_level=CalendarShareLevel.VIEW_ALL,
                    confidential_level=CalendarShareLevel.VIEW_ALL,
                    private_level=CalendarShareLevel.VIEW_ALL,
                    can_create=False,
                    can_delete=False,
                )
            else:
                # TODO: lookup shared permissions from the ACL module, then cap below
                base = CalendarPermissions.denied()
            return self._cap_ics_permissions(base)
        if is_owner:
            return CalendarPermissions.owner()
        # TODO: lookup real permissions from the ACL module
        return CalendarPermissions.denied()

    def check_permission(self, permissions: CalendarPermissions | None, action: CalendarPermissionAction,
                         event: CalEvent | None = None, calendar_user: CalendarUser | None = None) -> None:
        """Raise ERROR_CALENDAR_ACCESS_DENIED if the action is not allowed.

        For VIEW/RESPOND/MODIFY, the action is allowed if ANY visibility class has a sufficient level.
        For CREATE/DELETE, the dedicated flags are checked.

        MODIFY_IF_ORG is conditional: it satisfies a MODIFY check only when ``event`` and
        ``calendar_user`` are provided and the acting user is the event's ORGANIZER. Event-level
        callers (update event/task) pass both; calendar-level MODIFY checks (no event) are
        never satisfied by MODIFY_IF_ORG alone.

        ``permissions`` must have been resolved beforehand (get_permissions); a None here
        is a flow bug, not a denial.
        """
        if permissions is None:
            raise BugException("check_permission called before permissions were resolved")
        if action == CalendarPermissionAction.VIEW:
            if not self._any_level_at_least(permissions, CalendarShareLevel.VIEW_DATETIME):
                raise RequestException(error=err.ERROR_CALENDAR_ACCESS_DENIED)
        elif action == CalendarPermissionAction.RESPOND:
            if not self._any_level_at_least(permissions, CalendarShareLevel.RESPOND):
                raise RequestException(error=err.ERROR_CALENDAR_ACCESS_DENIED)
        elif action == CalendarPermissionAction.MODIFY:
            has_full_modify: bool = self._any_level_at_least(permissions, CalendarShareLevel.MODIFY)
            # MODIFY_IF_ORG only grants MODIFY with an event context where the acting user is the
            # organizer; without that context (calendar-level checks) it is never enough.
            has_conditional_modify: bool = (
                event is not None and calendar_user is not None
                and self._any_level_at_least(permissions, CalendarShareLevel.MODIFY_IF_ORG)
                and event.is_organized_by(calendar_user.user.mail)
            )
            if not has_full_modify and not has_conditional_modify:
                raise RequestException(error=err.ERROR_CALENDAR_ACCESS_DENIED)
        elif action == CalendarPermissionAction.CREATE:
            if not permissions.can_create:
                raise RequestException(error=err.ERROR_CALENDAR_ACCESS_DENIED)
        elif action == CalendarPermissionAction.DELETE:
            if not permissions.can_delete:
                raise RequestException(error=err.ERROR_CALENDAR_ACCESS_DENIED)

    def sanitize_events(self, events: list[CalEvent], permissions: CalendarPermissions) -> list[CalEvent]:
        """Mask event fields based on the user's permission level per visibility class.

        - NONE: event is excluded entirely
        - VIEW_DATETIME: only date_start, date_end, all_day visible; title replaced with "Busy"
        - VIEW_ALL and above: all fields visible
        """
        result: list[CalEvent] = []
        for event in events:
            level: CalendarShareLevel = permissions.level_for_visibility(event.visibility)
            if level == CalendarShareLevel.NONE:
                continue
            if level == CalendarShareLevel.VIEW_DATETIME:
                result.append(self._mask_event(event))
            else:
                result.append(event)
        return result

    @staticmethod
    def _mask_event(event: CalEvent) -> CalEvent:
        """Return a copy of the event with sensitive fields masked."""
        masked: CalEvent = dataclasses.replace(event)
        masked.title = _BUSY_TITLE
        masked.description = None
        masked.location = None
        masked.attendees = []
        masked.organizer = None
        masked.reminders = []
        masked.categories = []
        masked.attachments = []
        masked.conference_data = None
        masked.url = None
        masked.extra_properties = {}
        return masked

    @staticmethod
    def _cap_ics_permissions(permissions: CalendarPermissions) -> CalendarPermissions:
        """Cap permission levels at VIEW_ALL for ICS calendars (events are never writable)."""
        return CalendarPermissions(
            public_level=min(permissions.public_level, CalendarShareLevel.VIEW_ALL),
            confidential_level=min(permissions.confidential_level, CalendarShareLevel.VIEW_ALL),
            private_level=min(permissions.private_level, CalendarShareLevel.VIEW_ALL),
            can_create=False,
            can_delete=permissions.can_delete,
        )

    @staticmethod
    def _any_level_at_least(permissions: CalendarPermissions, minimum: CalendarShareLevel) -> bool:
        """Return True if any visibility class has a level >= minimum.

        CalendarShareLevel is an IntEnum ordered by capability:
        NONE(0) < VIEW_DATETIME(1) < VIEW_ALL(2) < RESPOND(3) < MODIFY_IF_ORG(4) < MODIFY(5)
        """
        return (permissions.public_level >= minimum
                or permissions.confidential_level >= minimum
                or permissions.private_level >= minimum)
