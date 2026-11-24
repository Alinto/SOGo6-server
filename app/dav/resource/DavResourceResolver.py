from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_ROOT_PATH
from app.dav.DavPath import DavPath
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavRootResource import DavRootResource
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.auth.User import User
    from app.dav.model.DavContext import DavContext
    from app.dav.resource.DavResource import DavResource


class DavResourceResolver:
    """Find the resource a request path targets, in the DAV tree of the account of the request (see DavPath)."""

    @staticmethod
    def resolve(path: str, context: DavContext) -> DavResource:
        """
        Return the resource targeted by a path.

        :param path: The path relative to the DAV root, percent-decoded, with or without its final "/"
        :type path: str
        :param context: The context of the request, with the authenticated user and the alias of its login
        :type context: DavContext
        :raises RequestException: ERROR_DAV_RESOURCE_NOT_FOUND for an unknown path, or a path of another
            account (another user, or another alias), whose existence is not disclosed
        :return: The resource
        :rtype: DavResource
        """
        normalized: str = DavPath.normalize(path)
        user: User = context.user
        account_alias: str | None = context.account_alias
        if normalized == DAV_ROOT_PATH:
            return DavRootResource(user=user, account_alias=account_alias)
        if normalized == DavPath.principal(user=user, account_alias=account_alias):
            return DavPrincipalResource(user=user, account_alias=account_alias)
        if normalized == DavPath.calendar_home(user=user, account_alias=account_alias):
            return DavCalendarHomeResource(user=user, account_alias=account_alias)
        if normalized == DavPath.addressbook_home(user=user, account_alias=account_alias):
            return DavAddressBookHomeResource(user=user, account_alias=account_alias)
        raise RequestException(error=err.ERROR_DAV_RESOURCE_NOT_FOUND)
