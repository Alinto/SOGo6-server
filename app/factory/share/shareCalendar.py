from __future__ import annotations

from typing import TYPE_CHECKING

from app.factory.share.share import Share
from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.model.enums.CalendarPermissionAction import CalendarPermissionAction
from app.module.calendar.model.enums.CalendarShareLevel import CalendarShareLevel
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.utils import constants as cs
from app.utils.strings import get_domain_from_mail

if TYPE_CHECKING:
    from app.factory.share.RepositoryAcl import AclEntry

# Discriminant stored in sogo6_acl.type for calendar shares.
CALENDAR_RESOURCE_TYPE: str = "calendar"

# API-facing share level strings (see CalendarShareRightsSchema) <-> internal CalendarShareLevel.
# MODIFY_IF_ORG is never exposed through the sharing API - it can only be reached by the
# CalendarAclEngine stub today (not settable by a user), so no API string maps to it.
_LEVEL_TO_STR: dict[CalendarShareLevel, str] = {
    CalendarShareLevel.NONE: "none",
    CalendarShareLevel.VIEW_DATETIME: "view-date-time",
    CalendarShareLevel.VIEW_ALL: "view-all",
    CalendarShareLevel.RESPOND: "respond-to",
    CalendarShareLevel.MODIFY: "modify",
}
_STR_TO_LEVEL: dict[str, CalendarShareLevel] = {v: k for k, v in _LEVEL_TO_STR.items()}

# Rights blob granted by POST /calendars/{key}/share (full modify access, per the endpoint's contract).
FULL_MODIFY_RIGHTS: dict = {
    "public": _LEVEL_TO_STR[CalendarShareLevel.MODIFY],
    "confidential": _LEVEL_TO_STR[CalendarShareLevel.MODIFY],
    "private": _LEVEL_TO_STR[CalendarShareLevel.MODIFY],
    "can_create_objects": True,
    "can_erase_objects": True,
}


class ShareCalendar(Share):
    """Sharing for calendars, backed by sogo6_acl (type='calendar').

    The rights blob stored per (calendar key, to_user) matches the API's CalendarShareRightsSchema:
    ``{"public": <level>, "confidential": <level>, "private": <level>,
    "can_create_objects": bool, "can_erase_objects": bool}`` where ``<level>`` is one of
    "none" | "view-date-time" | "view-all" | "respond-to" | "modify".

    ``rights_needed`` passed to ``check_permissions`` is either:
    - a bare ``CalendarPermissionAction.CREATE`` / ``CalendarPermissionAction.DELETE``
      (checked against the calendar-wide ``can_create_objects`` / ``can_erase_objects`` flags), or
    - a ``(CalendarPermissionAction, EventVisibility)`` tuple for VIEW / RESPOND / MODIFY, checked
      against the level of the matching visibility class.
    """

    resource_type: str = CALENDAR_RESOURCE_TYPE

    def get_user_or_anyone(self, for_user_uid: str, owner_uid: str, on_key: str) -> AclEntry | None:
        """Resolve the ACL entry granting for_user_uid access to on_key.

        Priority: an entry addressed specifically to for_user_uid; failing that, the "anyone"
        pseudo entry (``cs.ANYONE_TO_USER``, "<default>") - but only when for_user_uid and
        owner_uid belong to the same mail domain, since an "anyone" share only ever means
        "anyone in the owner's domain".
        """
        entry: AclEntry | None = self.get_entry(for_user_uid, on_key)
        if entry is not None:
            return entry
        user_domain: str | None = get_domain_from_mail(for_user_uid)
        owner_domain: str | None = get_domain_from_mail(owner_uid)
        if not user_domain or user_domain != owner_domain:
            return None
        return self.get_entry(cs.ANYONE_TO_USER, on_key)

    @staticmethod
    def level_for_visibility(rights: dict, visibility: EventVisibility) -> CalendarShareLevel:
        """Return the CalendarShareLevel granted for a given event visibility class."""
        key: str = {
            EventVisibility.CONFIDENTIAL: "confidential",
            EventVisibility.PRIVATE: "private",
        }.get(visibility, "public")
        return _STR_TO_LEVEL.get(rights.get(key, "none"), CalendarShareLevel.NONE)

    @staticmethod
    def to_calendar_permissions(rights: dict) -> CalendarPermissions:
        """Convert a stored rights blob into a CalendarPermissions, for CalendarAclEngine."""
        return CalendarPermissions(
            public_level=ShareCalendar.level_for_visibility(rights, EventVisibility.PUBLIC),
            confidential_level=ShareCalendar.level_for_visibility(rights, EventVisibility.CONFIDENTIAL),
            private_level=ShareCalendar.level_for_visibility(rights, EventVisibility.PRIVATE),
            can_create=bool(rights.get("can_create_objects", False)),
            can_delete=bool(rights.get("can_erase_objects", False)),
        )

    def _rights_satisfy(self, rights: dict, rights_needed: CalendarPermissionAction | tuple[CalendarPermissionAction, EventVisibility]) -> bool:
        if isinstance(rights_needed, tuple):
            action, visibility = rights_needed
        else:
            action, visibility = rights_needed, EventVisibility.PUBLIC

        if action == CalendarPermissionAction.CREATE:
            return bool(rights.get("can_create_objects", False))
        if action == CalendarPermissionAction.DELETE:
            return bool(rights.get("can_erase_objects", False))

        level: CalendarShareLevel = self.level_for_visibility(rights, visibility)
        if action == CalendarPermissionAction.VIEW:
            return level >= CalendarShareLevel.VIEW_DATETIME
        if action == CalendarPermissionAction.RESPOND:
            return level >= CalendarShareLevel.RESPOND
        if action == CalendarPermissionAction.MODIFY:
            return level >= CalendarShareLevel.MODIFY
        return False
