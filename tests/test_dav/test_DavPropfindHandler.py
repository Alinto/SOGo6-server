"""Unit tests for DavPropfindHandler - the body is given parsed and the multistatus is captured before XML."""

from http import HTTPStatus
from types import SimpleNamespace

import pytest

from app.auth.User import User
from app.dav.handler.DavPropfindHandler import DavPropfindHandler
from app.dav.model.DavContext import DavContext
from app.dav.model.DavRequest import DavRequest
from app.dav.resource import DavResourceResolver as resolver_module
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavPropResponse import DavPropResponse
from app.manager.dav.protocol.model.DavResourceType import DavResourceType
from app.manager.dav.protocol.model.enums.PropfindKind import PropfindKind
from app.manager.dav.protocol.model.PropfindRequest import PropfindRequest
from app.utils import errors as err
from app.utils.exceptions import RequestException

PRINCIPAL = "/dav/alice@example.org/"
DISPLAYNAME = "{DAV:}displayname"
GETETAG = "{DAV:}getetag"
CALENDAR_HOME_SET = "{urn:ietf:params:xml:ns:caldav}calendar-home-set"


class FakePropfindDeserializer:
    def __init__(self, result):
        self.result = result
        self.bodies = []

    def deserialize(self, data):
        self.bodies.append(data)
        return self.result


class FakeMultistatusSerializer:
    def __init__(self):
        self.multistatuses = []

    def serialize(self, data):
        self.multistatuses.append(data)
        return b"<multistatus/>"


class FakeCalendarInterface:
    def __init__(self, **_):
        pass

    def get_all_calendars(self):
        return {}


@pytest.fixture(autouse=True)
def calendar_interface(monkeypatch):
    monkeypatch.setattr(resolver_module, "InterfaceDavCalendar", FakeCalendarInterface)


def _context():
    user = User("alice@example.org", "secret", cn="Alice Martin")
    user.mail = "alice@example.org"
    return DavContext(
        process_settings=SimpleNamespace(),
        system_settings={},
        user_domain_settings={},
        user=user,
        cache=SimpleNamespace(),
        account_alias=None,
    )


CONTEXT = _context()


def _request(depth="0"):
    headers = {} if depth is None else {"depth": depth}
    return DavRequest(method="PROPFIND", path="alice@example.org/", headers=headers, body=b"<propfind/>")


def _handler(propfind):
    handler = DavPropfindHandler(authenticator=None)
    handler._deserializer = FakePropfindDeserializer(propfind)
    handler._serializer = FakeMultistatusSerializer()
    return handler


def _process(propfind, depth="0"):
    """Run a PROPFIND on the principal, return the response and the multistatus given to the serializer."""
    handler = _handler(propfind)
    response = handler.process(_request(depth), CONTEXT)
    return response, handler._serializer.multistatuses[0]


# ========== Tests for Depth ==========


def test_depth_0_resource_only():
    response, multistatus = _process(PropfindRequest(kind=PropfindKind.PROP, props=(DISPLAYNAME,)))
    assert response.status == HTTPStatus.MULTI_STATUS
    assert response.headers == {"Content-Type": "application/xml; charset=utf-8"}
    assert response.body == b"<multistatus/>"
    assert [prop_response.href for prop_response in multistatus.responses] == [PRINCIPAL]


def test_depth_1_with_members():
    _, multistatus = _process(PropfindRequest(kind=PropfindKind.PROP, props=(DISPLAYNAME,)), depth="1")
    assert [prop_response.href for prop_response in multistatus.responses] == [
        PRINCIPAL,
        PRINCIPAL + "Calendar/",
        PRINCIPAL + "Contacts/",
    ]


@pytest.mark.parametrize(
    "depth, error",
    [
        (None, err.ERROR_DAV_PROPFIND_INFINITE_DEPTH),
        ("infinity", err.ERROR_DAV_PROPFIND_INFINITE_DEPTH),
        ("Infinity", err.ERROR_DAV_PROPFIND_INFINITE_DEPTH),
        ("2", err.ERROR_DAV_DEPTH_INVALID),
        ("foo", err.ERROR_DAV_DEPTH_INVALID),
    ],
)
def test_depth_refused(depth, error):
    handler = _handler(PropfindRequest(kind=PropfindKind.ALLPROP))
    with pytest.raises(RequestException) as ex:
        handler.process(_request(depth), CONTEXT)
    assert ex.value.error is error
    assert not handler._deserializer.bodies


# ========== Tests for the properties asked ==========


def test_prop_found_and_missing():
    _, multistatus = _process(PropfindRequest(kind=PropfindKind.PROP, props=(DISPLAYNAME, GETETAG, DISPLAYNAME)))
    assert multistatus.responses == (
        DavPropResponse(href=PRINCIPAL, found={DISPLAYNAME: "Alice Martin"}, missing=(GETETAG,)),
    )


def test_propname():
    _, multistatus = _process(PropfindRequest(kind=PropfindKind.PROPNAME))
    names = DavPrincipalResource(
        user=CONTEXT.user, account_alias=None, calendar_interface=FakeCalendarInterface()
    ).properties()
    assert multistatus.responses == (DavPropResponse(href=PRINCIPAL, found={name: "" for name in names}),)


def test_allprop_webdav_and_included_properties():
    _, multistatus = _process(PropfindRequest(kind=PropfindKind.ALLPROP, props=(CALENDAR_HOME_SET, GETETAG)))
    assert multistatus.responses == (
        DavPropResponse(
            href=PRINCIPAL,
            found={
                "{DAV:}resourcetype": DavResourceType(types=("{DAV:}collection", "{DAV:}principal")),
                DISPLAYNAME: "Alice Martin",
                CALENDAR_HOME_SET: DavHrefs(hrefs=(PRINCIPAL + "Calendar/",)),
            },
            missing=(GETETAG,),
        ),
    )
