"""Unit tests for DavMultistatusSerializerXml - the bodies are compared to the expected XML."""

from xml.etree.ElementTree import fromstring

from app.manager.dav.protocol.model.DavComponentSet import DavComponentSet
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavMultistatus import DavMultistatus
from app.manager.dav.protocol.model.DavPrivilegeSet import DavPrivilegeSet
from app.manager.dav.protocol.model.DavPropResponse import DavPropResponse
from app.manager.dav.protocol.model.DavResourceType import DavResourceType
from app.manager.dav.protocol.model.DavSupportedPrivilege import DavSupportedPrivilege
from app.manager.dav.protocol.model.DavSupportedPrivilegeSet import DavSupportedPrivilegeSet
from app.manager.dav.protocol.serializer.DavMultistatusSerializerXml import DavMultistatusSerializerXml

DECLARATION = b"<?xml version='1.0' encoding='utf-8'?>\n"
CALENDAR_HOME_SET = "{urn:ietf:params:xml:ns:caldav}calendar-home-set"

_serializer = DavMultistatusSerializerXml()


def _serialize(*responses):
    return _serializer.serialize(DavMultistatus(responses=responses))


# ========== Tests for serialize ==========


def test_found_and_missing_properties():
    body = _serialize(
        DavPropResponse(
            href="/dav/alice@example.org/",
            found={
                "{DAV:}displayname": "Alice",
                "{DAV:}resourcetype": DavResourceType(types=("{DAV:}collection",)),
                CALENDAR_HOME_SET: DavHrefs(hrefs=("/dav/alice@example.org/Calendar/",)),
            },
            missing=("{DAV:}getetag",),
        )
    )
    assert body == (
        DECLARATION + b'<D:multistatus xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:"><D:response>'
        b"<D:href>/dav/alice@example.org/</D:href>"
        b"<D:propstat><D:prop><D:displayname>Alice</D:displayname>"
        b"<D:resourcetype><D:collection /></D:resourcetype>"
        b"<C:calendar-home-set><D:href>/dav/alice@example.org/Calendar/</D:href></C:calendar-home-set>"
        b"</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
        b"<D:propstat><D:prop><D:getetag /></D:prop><D:status>HTTP/1.1 404 Not Found</D:status></D:propstat>"
        b"</D:response></D:multistatus>"
    )


def test_one_response_per_resource():
    body = _serialize(
        DavPropResponse(href="/dav/"),
        DavPropResponse(href="/dav/alice@example.org/", found={"{DAV:}displayname": "Alice"}),
    )
    assert body == (
        DECLARATION + b'<D:multistatus xmlns:D="DAV:">'
        b"<D:response><D:href>/dav/</D:href>"
        b"<D:propstat><D:prop /><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>"
        b"<D:response><D:href>/dav/alice@example.org/</D:href>"
        b"<D:propstat><D:prop><D:displayname>Alice</D:displayname></D:prop>"
        b"<D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>"
        b"</D:multistatus>"
    )


def test_missing_properties_only():
    body = _serialize(DavPropResponse(href="/dav/alice@example.org/", missing=("{DAV:}getetag",)))
    assert body == (
        DECLARATION + b'<D:multistatus xmlns:D="DAV:"><D:response>'
        b"<D:href>/dav/alice@example.org/</D:href>"
        b"<D:propstat><D:prop><D:getetag /></D:prop><D:status>HTTP/1.1 404 Not Found</D:status></D:propstat>"
        b"</D:response></D:multistatus>"
    )


def test_forbidden_characters_removed():
    body = _serialize(DavPropResponse(href="/dav/", found={"{DAV:}displayname": "Week\x01\x0b\ud800ly\tplan"}))
    assert body == (
        DECLARATION + b'<D:multistatus xmlns:D="DAV:"><D:response><D:href>/dav/</D:href>'
        b"<D:propstat><D:prop><D:displayname>Weekly\tplan</D:displayname></D:prop>"
        b"<D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response></D:multistatus>"
    )


def test_href_percent_encoded():
    path = "/dav/alice+tag@example.org/Calendar/r\u00e9union 50%/"
    body = _serialize(DavPropResponse(href=path, found={CALENDAR_HOME_SET: DavHrefs(hrefs=(path,))}))
    assert [href.text for href in fromstring(body).iter("{DAV:}href")] == [
        "/dav/alice+tag@example.org/Calendar/r%C3%A9union%2050%25/"
    ] * 2


def test_component_and_privilege_sets():
    body = _serialize(
        DavPropResponse(
            href="/dav/",
            found={
                "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set": DavComponentSet(
                    components=("VEVENT", "VTODO")
                ),
                "{DAV:}current-user-privilege-set": DavPrivilegeSet(privileges=("{DAV:}read",)),
            },
        )
    )
    assert body == (
        DECLARATION + b'<D:multistatus xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:"><D:response>'
        b"<D:href>/dav/</D:href><D:propstat><D:prop>"
        b'<C:supported-calendar-component-set><C:comp name="VEVENT" /><C:comp name="VTODO" />'
        b"</C:supported-calendar-component-set>"
        b"<D:current-user-privilege-set><D:privilege><D:read /></D:privilege></D:current-user-privilege-set>"
        b"</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response></D:multistatus>"
    )


def test_supported_privilege_tree():
    read_free_busy = DavSupportedPrivilege(
        privilege="{urn:ietf:params:xml:ns:caldav}read-free-busy", description="Free busy"
    )
    tree = DavSupportedPrivilegeSet(
        privileges=(
            DavSupportedPrivilege(privilege="{DAV:}all", description="All", abstract=True, contained=(read_free_busy,)),
        )
    )
    body = _serialize(DavPropResponse(href="/dav/", found={"{DAV:}supported-privilege-set": tree}))
    assert body == (
        DECLARATION + b'<D:multistatus xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:"><D:response>'
        b"<D:href>/dav/</D:href><D:propstat><D:prop><D:supported-privilege-set>"
        b'<D:supported-privilege><D:privilege><D:all /></D:privilege><D:abstract /><D:description xml:lang="en">All'
        b"</D:description>"
        b"<D:supported-privilege><D:privilege><C:read-free-busy /></D:privilege>"
        b'<D:description xml:lang="en">Free busy</D:description></D:supported-privilege>'
        b"</D:supported-privilege></D:supported-privilege-set>"
        b"</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response></D:multistatus>"
    )
