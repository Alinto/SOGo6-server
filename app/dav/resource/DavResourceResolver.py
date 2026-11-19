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
from app.utils.strings import lower_login_domain

if TYPE_CHECKING:
    from app.auth.User import User
    from app.dav.resource.DavResource import DavResource


class DavResourceResolver:
    """Find the resource a request path targets, in the DAV tree of the authenticated user (see DavPath)."""

    @staticmethod
    def resolve(path: str, user: User) -> DavResource:
        """
        Return the resource targeted by a path.

        :param path: The path relative to the DAV root, percent-decoded, with or without its final "/"
        :type path: str
        :param user: The authenticated user
        :type user: User
        :raises RequestException: ERROR_DAV_RESOURCE_NOT_FOUND for an unknown path, or a path of another
            user, whose existence is not disclosed
        :return: The resource
        :rtype: DavResource
        """
        segments: list[str] = [segment for segment in path.split("/") if segment]
        if not segments:
            return DavRootResource(user)
        # The login of the path is compared as the login of the Basic authentication
        segments[0] = lower_login_domain(segments[0])
        normalized: str = DAV_ROOT_PATH + "".join(f"{segment}/" for segment in segments)
        if normalized == DavPath.principal(user):
            return DavPrincipalResource(user)
        if normalized == DavPath.calendar_home(user):
            return DavCalendarHomeResource(user)
        if normalized == DavPath.addressbook_home(user):
            return DavAddressBookHomeResource(user)
        raise RequestException(error=err.ERROR_DAV_RESOURCE_NOT_FOUND)
