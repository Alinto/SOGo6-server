from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ACCOUNT_ALIAS_SEPARATOR, DAV_ADDRESSBOOK_HOME, DAV_CALENDAR_HOME, DAV_ROOT_PATH
from app.utils.strings import lower_login_domain

if TYPE_CHECKING:
    from app.auth.User import User


class DavPath:
    """Paths of the DAV tree of an account, absolute, not percent-encoded and ending with "/":

    /dav/                        root
    /dav/<account>/              principal
    /dav/<account>/Calendar/     home of the calendars
    /dav/<account>/Contacts/     home of the address books

    <account> is the login of the user, followed by "!<alias>" for an account signed in with an alias.
    """

    @staticmethod
    def normalize(path: str) -> str:
        """Return a request path in the form of the paths built here, to compare them: absolute, without empty
        segment, ending with "/". The account is read as the Basic login: the domain of the login is lowered,
        its alias is kept as is.

        :param path: The path relative to the DAV root, percent-decoded, with or without its final "/"
        :type path: str
        :return: The normalized path
        :rtype: str
        """
        segments: list[str] = [segment for segment in path.split("/") if segment]
        if segments:
            login, separator, account_alias = segments[0].partition(DAV_ACCOUNT_ALIAS_SEPARATOR)
            segments[0] = lower_login_domain(login) + separator + account_alias
        return DAV_ROOT_PATH + "".join(f"{segment}/" for segment in segments)

    @staticmethod
    def principal(user: User, account_alias: str | None) -> str:
        """Return the path of the principal of the account of a user, with the alias of its login if any."""
        account: str = user.uid
        if account_alias is not None:
            account += DAV_ACCOUNT_ALIAS_SEPARATOR + account_alias
        return f"{DAV_ROOT_PATH}{account}/"

    @staticmethod
    def calendar_home(user: User, account_alias: str | None) -> str:
        """Return the path of the home of the calendars of the account of a user."""
        return f"{DavPath.principal(user=user, account_alias=account_alias)}{DAV_CALENDAR_HOME}/"

    @staticmethod
    def addressbook_home(user: User, account_alias: str | None) -> str:
        """Return the path of the home of the address books of the account of a user."""
        return f"{DavPath.principal(user=user, account_alias=account_alias)}{DAV_ADDRESSBOOK_HOME}/"
