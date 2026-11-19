from app.auth.User import User
from app.dav.DavPath import DavPath
from app.manager.dav.protocol.DavProtocolConst import (
    CALDAV_CALENDAR_HOME_SET,
    CALDAV_CALENDAR_USER_ADDRESS_SET,
    CARDDAV_ADDRESSBOOK_HOME_SET,
    DAV_ALTERNATE_URI_SET,
    DAV_DISPLAYNAME,
    DAV_GROUP_MEMBERSHIP,
    DAV_PRINCIPAL_URL,
)
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavPropResponse import DavPropValue
from app.utils.serializer.Serializer import Serializer


class UserSerializerDavProps(Serializer[User, dict[str, DavPropValue]]):
    """Convert a user into the properties of its principal, by name in Clark notation."""

    def serialize(self, data: User) -> dict[str, DavPropValue]:
        """Return the name of the user, its principal URL, its homes and its addresses."""
        principal: str = DavPath.principal(data)
        # The aliases too: an invitation sent to an alias is matched to the principal (RFC 6638 section 2.4.1)
        mails: list[str] = ([data.mail] if data.mail else []) + data.extra_mail
        return {
            DAV_DISPLAYNAME: data.cn or data.uid,
            DAV_PRINCIPAL_URL: DavHrefs(hrefs=(principal,)),
            # Required by RFC 3744 section 4, empty: no alternate URI, no group
            DAV_ALTERNATE_URI_SET: DavHrefs(hrefs=()),
            DAV_GROUP_MEMBERSHIP: DavHrefs(hrefs=()),
            CALDAV_CALENDAR_HOME_SET: DavHrefs(hrefs=(DavPath.calendar_home(data),)),
            CARDDAV_ADDRESSBOOK_HOME_SET: DavHrefs(hrefs=(DavPath.addressbook_home(data),)),
            CALDAV_CALENDAR_USER_ADDRESS_SET: DavHrefs(hrefs=tuple(f"mailto:{mail}" for mail in mails)),
        }
