from __future__ import annotations
from typing import TYPE_CHECKING

from app.dav.DavConst import DAV_DEFAULT_COLLECTION, DAV_ROOT_PATH
from app.dav.DavPath import DavPath
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavCalendarResource import DavCalendarResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavRootResource import DavRootResource
from app.dav.serializer.CalCalendarSerializerDavProps import CalCalendarSerializerDavProps
from app.interface.calendar.InterfaceDavCalendar import InterfaceDavCalendar
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.auth.User import User
    from app.dav.model.DavContext import DavContext
    from app.dav.resource.DavResource import DavResource
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue


class DavResourceResolver:
    """Find the resource a request path targets, in the DAV tree of the account of the request (see DavPath).

    The calendar interface is built for every request from its context: the root and the principal need it to
    build their members, down to the home of the calendars. It is given the choices of the DAV server: the
    serializer of the properties of a calendar and the name of the default calendar in the paths.
    """

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
        calendar_interface: InterfaceDavCalendar = InterfaceDavCalendar(
            process_setting=context.process_settings,
            user=user,
            cache=context.cache,
            calendar_serializer=CalCalendarSerializerDavProps(),
            default_calendar_name=DAV_DEFAULT_COLLECTION,
        )
        calendar_home: str = DavPath.calendar_home(user=user, account_alias=account_alias)
        if normalized == DAV_ROOT_PATH:
            return DavRootResource(user=user, account_alias=account_alias, calendar_interface=calendar_interface)
        if normalized == DavPath.principal(user=user, account_alias=account_alias):
            return DavPrincipalResource(user=user, account_alias=account_alias, calendar_interface=calendar_interface)
        if normalized == calendar_home:
            return DavCalendarHomeResource(
                user=user, account_alias=account_alias, calendar_interface=calendar_interface
            )
        if normalized.startswith(calendar_home):
            return DavResourceResolver._resolve_calendar(
                name=normalized.removeprefix(calendar_home).removesuffix("/"),
                user=user,
                account_alias=account_alias,
                calendar_interface=calendar_interface,
            )
        if normalized == DavPath.addressbook_home(user=user, account_alias=account_alias):
            return DavAddressBookHomeResource(user=user, account_alias=account_alias)
        raise RequestException(error=err.ERROR_DAV_RESOURCE_NOT_FOUND)

    @staticmethod
    def _resolve_calendar(
        name: str, user: User, account_alias: str | None, calendar_interface: InterfaceDavCalendar
    ) -> DavCalendarResource:
        """Return the calendar of the user named in the path (see InterfaceDavCalendar.get_calendar).

        :raises RequestException: ERROR_DAV_RESOURCE_NOT_FOUND for an unknown name, or a path below a calendar
        """
        if "/" not in name:
            properties: dict[str, DavPropValue] | None = calendar_interface.get_calendar(name)
            if properties is not None:
                return DavCalendarResource(user=user, account_alias=account_alias, name=name, properties=properties)
        raise RequestException(error=err.ERROR_DAV_RESOURCE_NOT_FOUND)
