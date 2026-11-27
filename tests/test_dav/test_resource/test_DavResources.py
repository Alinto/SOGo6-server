"""Unit tests for the resources of the DAV tree: properties and members."""

from app.auth.User import User
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavCalendarResource import DavCalendarResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavRootResource import DavRootResource
from app.dav.serializer.UserSerializerDavProps import UserSerializerDavProps
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavPrivilegeSet import DavPrivilegeSet
from app.manager.dav.protocol.model.DavResourceType import DavResourceType
from app.manager.dav.protocol.model.DavSupportedPrivilege import DavSupportedPrivilege
from app.manager.dav.protocol.model.DavSupportedPrivilegeSet import DavSupportedPrivilegeSet

PRINCIPAL = "/dav/alice@example.org/"
ALIAS_PRINCIPAL = "/dav/alice@example.org!work/"
COLLECTION = "{DAV:}collection"
CURRENT_USER_PRINCIPAL = "{DAV:}current-user-principal"
PRINCIPAL_URL = "{DAV:}principal-URL"
ADDRESSBOOK_HOME_SET = "{urn:ietf:params:xml:ns:carddav}addressbook-home-set"
DEFAULT_CALENDAR = {"{DAV:}displayname": "Personal"}
WORK_CALENDAR = {"{DAV:}displayname": "Work", "{urn:ietf:params:xml:ns:caldav}calendar-timezone": "VTIMEZONE"}


class FakeCalendarInterface:
    def __init__(self, calendars=None):
        self.calendars = calendars or {}

    def get_all_calendars(self):
        return self.calendars


def _user():
    user = User("alice@example.org", "secret", cn="Alice Martin")
    user.mail = "alice@example.org"
    return user


USER = _user()

# ========== Tests for DavRootResource ==========


def test_root():
    root = DavRootResource(user=USER, account_alias=None, calendar_interface=FakeCalendarInterface())
    assert root.path == "/dav/"
    assert root.properties() == {
        "{DAV:}resourcetype": DavResourceType(types=(COLLECTION,)),
        CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
    }
    assert [child.path for child in root.children()] == [PRINCIPAL]


# ========== Tests for DavPrincipalResource ==========


def test_principal():
    principal = DavPrincipalResource(user=USER, account_alias=None, calendar_interface=FakeCalendarInterface())
    assert principal.path == PRINCIPAL
    assert principal.properties() == {
        "{DAV:}resourcetype": DavResourceType(types=(COLLECTION, "{DAV:}principal")),
        CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
        PRINCIPAL_URL: DavHrefs(hrefs=(PRINCIPAL,)),
        "{urn:ietf:params:xml:ns:caldav}calendar-home-set": DavHrefs(hrefs=(PRINCIPAL + "Calendar/",)),
        ADDRESSBOOK_HOME_SET: DavHrefs(hrefs=(PRINCIPAL + "Contacts/",)),
        **UserSerializerDavProps().serialize(USER),
    }
    assert [child.path for child in principal.children()] == [PRINCIPAL + "Calendar/", PRINCIPAL + "Contacts/"]


# ========== Tests for the homes ==========


def test_homes():
    for home, name in (
        (
            DavCalendarHomeResource(user=USER, account_alias=None, calendar_interface=FakeCalendarInterface()),
            "Calendar",
        ),
        (DavAddressBookHomeResource(user=USER, account_alias=None), "Contacts"),
    ):
        assert home.path == f"{PRINCIPAL}{name}/"
        assert home.properties() == {
            "{DAV:}resourcetype": DavResourceType(types=(COLLECTION,)),
            CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
            "{DAV:}displayname": name,
        }
        assert not home.children()


def test_calendar_home_lists_calendars():
    interface = FakeCalendarInterface({"personal": DEFAULT_CALENDAR, "k-work": WORK_CALENDAR})
    home = DavCalendarHomeResource(user=USER, account_alias=None, calendar_interface=interface)
    assert [child.path for child in home.children()] == [
        PRINCIPAL + "Calendar/personal/",
        PRINCIPAL + "Calendar/k-work/",
    ]


# ========== Tests for DavCalendarResource ==========


def test_calendar():
    calendar = DavCalendarResource(user=USER, account_alias=None, name="k-work", properties=WORK_CALENDAR)
    assert calendar.path == PRINCIPAL + "Calendar/k-work/"
    read_free_busy = "{urn:ietf:params:xml:ns:caldav}read-free-busy"
    assert calendar.properties() == {
        "{DAV:}resourcetype": DavResourceType(types=(COLLECTION, "{urn:ietf:params:xml:ns:caldav}calendar")),
        CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
        **WORK_CALENDAR,
        "{DAV:}supported-privilege-set": DavSupportedPrivilegeSet(
            privileges=(
                DavSupportedPrivilege(
                    privilege="{DAV:}read",
                    description="Read the calendar and its objects",
                    contained=(DavSupportedPrivilege(privilege=read_free_busy, description="Read the free busy time"),),
                ),
            )
        ),
        "{DAV:}current-user-privilege-set": DavPrivilegeSet(privileges=("{DAV:}read", read_free_busy)),
    }
    assert not calendar.children()


# ========== Tests for the account alias ==========


def test_alias_paths():
    interface = FakeCalendarInterface({"personal": DEFAULT_CALENDAR})
    root = DavRootResource(user=USER, account_alias="work", calendar_interface=interface)
    assert root.properties()[CURRENT_USER_PRINCIPAL] == DavHrefs(hrefs=(ALIAS_PRINCIPAL,))
    principal = root.children()[0]
    assert principal.path == ALIAS_PRINCIPAL
    assert principal.properties()[PRINCIPAL_URL] == DavHrefs(hrefs=(ALIAS_PRINCIPAL,))
    assert principal.properties()[ADDRESSBOOK_HOME_SET] == DavHrefs(hrefs=(ALIAS_PRINCIPAL + "Contacts/",))
    assert [child.path for child in principal.children()] == [
        ALIAS_PRINCIPAL + "Calendar/",
        ALIAS_PRINCIPAL + "Contacts/",
    ]
    assert [child.path for child in principal.children()[0].children()] == [ALIAS_PRINCIPAL + "Calendar/personal/"]
