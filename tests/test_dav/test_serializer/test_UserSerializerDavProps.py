"""Unit tests for UserSerializerDavProps."""

from app.auth.User import User
from app.dav.serializer.UserSerializerDavProps import UserSerializerDavProps
from app.manager.dav.protocol.model.DavHrefs import DavHrefs

PRINCIPAL = "/dav/alice@example.org/"
CALENDAR_USER_ADDRESS_SET = "{urn:ietf:params:xml:ns:caldav}calendar-user-address-set"


def _user(mail="alice@example.org", extra_mail=None):
    user = User("alice@example.org", "secret", cn="Alice Martin")
    user.mail = mail
    user.extra_mail = extra_mail or []
    return user


# ========== Tests for serialize ==========


def test_serialize():
    assert UserSerializerDavProps().serialize(_user(extra_mail=["a.martin@example.org"])) == {
        "{DAV:}displayname": "Alice Martin",
        "{DAV:}principal-URL": DavHrefs(hrefs=(PRINCIPAL,)),
        "{DAV:}alternate-URI-set": DavHrefs(hrefs=()),
        "{DAV:}group-membership": DavHrefs(hrefs=()),
        "{urn:ietf:params:xml:ns:caldav}calendar-home-set": DavHrefs(hrefs=(PRINCIPAL + "Calendar/",)),
        "{urn:ietf:params:xml:ns:carddav}addressbook-home-set": DavHrefs(hrefs=(PRINCIPAL + "Contacts/",)),
        CALENDAR_USER_ADDRESS_SET: DavHrefs(hrefs=("mailto:alice@example.org", "mailto:a.martin@example.org")),
    }


def test_serialize_without_mail():
    assert UserSerializerDavProps().serialize(_user(mail=""))[CALENDAR_USER_ADDRESS_SET] == DavHrefs(hrefs=())
