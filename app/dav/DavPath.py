from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ADDRESSBOOK_HOME, DAV_CALENDAR_HOME, DAV_ROOT_PATH

if TYPE_CHECKING:
    from app.auth.User import User


class DavPath:
    """Paths of the DAV tree of a user, absolute, not percent-encoded and ending with "/":

    /dav/                      root
    /dav/<login>/              principal
    /dav/<login>/Calendar/     home of the calendars
    /dav/<login>/Contacts/     home of the address books
    """

    @staticmethod
    def principal(user: User) -> str:
        """Return the path of the principal of a user."""
        return f"{DAV_ROOT_PATH}{user.uid}/"

    @staticmethod
    def calendar_home(user: User) -> str:
        """Return the path of the home of the calendars of a user."""
        return f"{DavPath.principal(user)}{DAV_CALENDAR_HOME}/"

    @staticmethod
    def addressbook_home(user: User) -> str:
        """Return the path of the home of the address books of a user."""
        return f"{DavPath.principal(user)}{DAV_ADDRESSBOOK_HOME}/"
