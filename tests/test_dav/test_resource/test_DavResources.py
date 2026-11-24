"""Unit tests for the resources of the DAV tree: properties and members."""

from app.auth.User import User
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavRootResource import DavRootResource
from app.dav.serializer.UserSerializerDavProps import UserSerializerDavProps
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavResourceType import DavResourceType

PRINCIPAL = "/dav/alice@example.org/"
ALIAS_PRINCIPAL = "/dav/alice@example.org!work/"
COLLECTION = "{DAV:}collection"
CURRENT_USER_PRINCIPAL = "{DAV:}current-user-principal"
PRINCIPAL_URL = "{DAV:}principal-URL"
ADDRESSBOOK_HOME_SET = "{urn:ietf:params:xml:ns:carddav}addressbook-home-set"


def _user():
    user = User("alice@example.org", "secret", cn="Alice Martin")
    user.mail = "alice@example.org"
    return user


USER = _user()

# ========== Tests for DavRootResource ==========


def test_root():
    root = DavRootResource(user=USER, account_alias=None)
    assert root.path == "/dav/"
    assert root.properties() == {
        "{DAV:}resourcetype": DavResourceType(types=(COLLECTION,)),
        CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
    }
    assert [child.path for child in root.children()] == [PRINCIPAL]


# ========== Tests for DavPrincipalResource ==========


def test_principal():
    principal = DavPrincipalResource(user=USER, account_alias=None)
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
        (DavCalendarHomeResource(user=USER, account_alias=None), "Calendar"),
        (DavAddressBookHomeResource(user=USER, account_alias=None), "Contacts"),
    ):
        assert home.path == f"{PRINCIPAL}{name}/"
        assert home.properties() == {
            "{DAV:}resourcetype": DavResourceType(types=(COLLECTION,)),
            CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
            "{DAV:}displayname": name,
        }
        assert not home.children()


# ========== Tests for the account alias ==========


def test_alias_paths():
    root = DavRootResource(user=USER, account_alias="work")
    assert root.properties()[CURRENT_USER_PRINCIPAL] == DavHrefs(hrefs=(ALIAS_PRINCIPAL,))
    principal = root.children()[0]
    assert principal.path == ALIAS_PRINCIPAL
    assert principal.properties()[PRINCIPAL_URL] == DavHrefs(hrefs=(ALIAS_PRINCIPAL,))
    assert principal.properties()[ADDRESSBOOK_HOME_SET] == DavHrefs(hrefs=(ALIAS_PRINCIPAL + "Contacts/",))
    assert [child.path for child in principal.children()] == [
        ALIAS_PRINCIPAL + "Calendar/",
        ALIAS_PRINCIPAL + "Contacts/",
    ]
