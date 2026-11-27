"""Unit tests for DavResourceResolver."""

from types import SimpleNamespace

import pytest

from app.auth.User import User
from app.dav.model.DavContext import DavContext
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource import DavResourceResolver as resolver_module
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavCalendarResource import DavCalendarResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavResourceResolver import DavResourceResolver
from app.dav.resource.DavRootResource import DavRootResource
from app.dav.serializer.CalCalendarSerializerDavProps import CalCalendarSerializerDavProps
from app.utils import errors as err
from app.utils.exceptions import RequestException

# Names found by the interface, the default calendar by "personal" and by its key
CALENDARS = {
    "personal": {"{DAV:}displayname": "Personal"},
    "k-default": {"{DAV:}displayname": "Personal"},
    "k-work": {"{DAV:}displayname": "Work"},
}


class FakeCalendarInterface:
    instances = []

    def __init__(self, process_setting, user, cache, calendar_serializer, default_calendar_name):
        self.built_with = (process_setting, user, cache)
        self.calendar_serializer = calendar_serializer
        self.default_calendar_name = default_calendar_name
        FakeCalendarInterface.instances.append(self)

    def get_calendar(self, name):
        return CALENDARS.get(name)


@pytest.fixture(autouse=True)
def calendar_interface(monkeypatch):
    monkeypatch.setattr(resolver_module, "InterfaceDavCalendar", FakeCalendarInterface)
    FakeCalendarInterface.instances = []


def _context(account_alias=None):
    return DavContext(
        process_settings=SimpleNamespace(),
        system_settings={},
        user_domain_settings={},
        user=User("alice@example.org", "secret"),
        cache=SimpleNamespace(),
        account_alias=account_alias,
    )


CONTEXT = _context()
ALIAS_CONTEXT = _context(account_alias="Work")

# ========== Tests for resolve ==========


@pytest.mark.parametrize(
    "path, resource_class",
    [
        ("", DavRootResource),
        ("alice@example.org/", DavPrincipalResource),
        ("alice@example.org", DavPrincipalResource),
        ("alice@EXAMPLE.org/", DavPrincipalResource),
        ("alice@example.org/Calendar/", DavCalendarHomeResource),
        ("alice@example.org/Contacts", DavAddressBookHomeResource),
        ("alice@example.org/Calendar/k-work", DavCalendarResource),
    ],
)
def test_resolve(path, resource_class):
    assert isinstance(DavResourceResolver.resolve(path=path, context=CONTEXT), resource_class)


def test_interface_built_from_context():
    DavResourceResolver.resolve(path="", context=CONTEXT)
    interface = FakeCalendarInterface.instances[0]
    assert interface.built_with == (CONTEXT.process_settings, CONTEXT.user, CONTEXT.cache)
    assert isinstance(interface.calendar_serializer, CalCalendarSerializerDavProps)
    assert interface.default_calendar_name == "personal"


@pytest.mark.parametrize("name", ["personal", "k-default"])
def test_resolve_default_calendar(name):
    calendar = DavResourceResolver.resolve(path=f"alice@example.org/Calendar/{name}/", context=CONTEXT)
    assert calendar.path == f"/dav/alice@example.org/Calendar/{name}/"
    assert calendar.properties()["{DAV:}displayname"] == "Personal"


@pytest.mark.parametrize(
    "path",
    [
        "bob@example.org/",
        "Alice@example.org/",
        "alice@example.org/Tasks/",
        "alice@example.org/Calendar/unknown/",
        "alice@example.org/Calendar/Personal/",
        "alice@example.org/Calendar/k-work/event.ics",
        "alice@example.org!Work/",
    ],
)
def test_resolve_not_found(path):
    with pytest.raises(RequestException) as ex:
        DavResourceResolver.resolve(path=path, context=CONTEXT)
    assert ex.value.error is err.ERROR_DAV_RESOURCE_NOT_FOUND


# ========== Tests for the account alias ==========


@pytest.mark.parametrize(
    "path, resource_class",
    [
        ("", DavRootResource),
        ("alice@EXAMPLE.org!Work/", DavPrincipalResource),
        ("alice@example.org!Work/Contacts/", DavAddressBookHomeResource),
        ("alice@example.org!Work/Calendar/personal/", DavCalendarResource),
    ],
)
def test_resolve_alias(path, resource_class):
    assert isinstance(DavResourceResolver.resolve(path=path, context=ALIAS_CONTEXT), resource_class)


@pytest.mark.parametrize("path", ["alice@example.org/", "alice@example.org!work/", "alice@example.org!Other/"])
def test_resolve_alias_not_found(path):
    with pytest.raises(RequestException) as ex:
        DavResourceResolver.resolve(path=path, context=ALIAS_CONTEXT)
    assert ex.value.error is err.ERROR_DAV_RESOURCE_NOT_FOUND
