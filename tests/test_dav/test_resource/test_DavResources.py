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
COLLECTION = "{DAV:}collection"
CURRENT_USER_PRINCIPAL = "{DAV:}current-user-principal"


def _user():
    user = User("alice@example.org", "secret", cn="Alice Martin")
    user.mail = "alice@example.org"
    return user


# ========== Tests for DavRootResource ==========


def test_root():
    root = DavRootResource(_user())
    assert root.path == "/dav/"
    assert root.properties() == {
        "{DAV:}resourcetype": DavResourceType(types=(COLLECTION,)),
        CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
    }
    assert [child.path for child in root.children()] == [PRINCIPAL]


# ========== Tests for DavPrincipalResource ==========


def test_principal():
    user = _user()
    principal = DavPrincipalResource(user)
    assert principal.path == PRINCIPAL
    assert principal.properties() == {
        "{DAV:}resourcetype": DavResourceType(types=(COLLECTION, "{DAV:}principal")),
        CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
        **UserSerializerDavProps().serialize(user),
    }
    assert [child.path for child in principal.children()] == [PRINCIPAL + "Calendar/", PRINCIPAL + "Contacts/"]


# ========== Tests for the homes ==========


def test_homes():
    for home, name in (
        (DavCalendarHomeResource(_user()), "Calendar"),
        (DavAddressBookHomeResource(_user()), "Contacts"),
    ):
        assert home.path == f"{PRINCIPAL}{name}/"
        assert home.properties() == {
            "{DAV:}resourcetype": DavResourceType(types=(COLLECTION,)),
            CURRENT_USER_PRINCIPAL: DavHrefs(hrefs=(PRINCIPAL,)),
            "{DAV:}displayname": name,
        }
        assert not home.children()
