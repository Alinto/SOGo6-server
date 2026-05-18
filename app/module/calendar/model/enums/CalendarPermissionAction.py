from __future__ import annotations

from enum import Enum


class CalendarPermissionAction(Enum):
    """Action that a user wants to perform on a calendar."""

    VIEW = "view"
    RESPOND = "respond"
    MODIFY = "modify"
    CREATE = "create"
    DELETE = "delete"
