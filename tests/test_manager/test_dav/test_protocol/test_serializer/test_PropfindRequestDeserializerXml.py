"""Unit tests for PropfindRequestDeserializerXml."""

import pytest

from app.manager.dav.protocol.model.enums.PropfindKind import PropfindKind
from app.manager.dav.protocol.model.PropfindRequest import PropfindRequest
from app.manager.dav.protocol.serializer.PropfindRequestDeserializerXml import PropfindRequestDeserializerXml
from app.utils import errors as err
from app.utils.exceptions import RequestException

_deserializer = PropfindRequestDeserializerXml()

# ========== Tests for deserialize ==========


@pytest.mark.parametrize("body", [b"", b" \r\n"])
def test_empty_body_is_allprop(body):
    assert _deserializer.deserialize(body) == PropfindRequest(kind=PropfindKind.ALLPROP)


def test_prop():
    body = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">'
        b"<D:prop><D:displayname/><C:calendar-home-set/></D:prop>"
        b"</D:propfind>"
    )
    assert _deserializer.deserialize(body) == PropfindRequest(
        kind=PropfindKind.PROP,
        props=("{DAV:}displayname", "{urn:ietf:params:xml:ns:caldav}calendar-home-set"),
    )


def test_propname():
    body = b'<propfind xmlns="DAV:"><propname/></propfind>'
    assert _deserializer.deserialize(body) == PropfindRequest(kind=PropfindKind.PROPNAME)


def test_allprop_with_include():
    body = (
        b'<propfind xmlns="DAV:"><allprop/>'
        b'<include><C:calendar-home-set xmlns:C="urn:ietf:params:xml:ns:caldav"/></include>'
        b"</propfind>"
    )
    assert _deserializer.deserialize(body) == PropfindRequest(
        kind=PropfindKind.ALLPROP, props=("{urn:ietf:params:xml:ns:caldav}calendar-home-set",)
    )


def test_unknown_elements_ignored():
    body = b'<propfind xmlns="DAV:" xmlns:X="urn:example"><X:unknown/><prop><displayname/></prop></propfind>'
    assert _deserializer.deserialize(body) == PropfindRequest(kind=PropfindKind.PROP, props=("{DAV:}displayname",))


def test_body_larger_than_a_chunk():
    body = b'<propfind xmlns="DAV:"><prop>' + b"<displayname/>" * 1000 + b"</prop></propfind>"
    assert _deserializer.deserialize(body) == PropfindRequest(
        kind=PropfindKind.PROP, props=("{DAV:}displayname",) * 1000
    )


@pytest.mark.parametrize(
    "body",
    [
        b'<propfind xmlns="DAV:"><prop>',
        b'<propertyupdate xmlns="DAV:"><set/></propertyupdate>',
        b'<propfind xmlns="DAV:"/>',
        b"<propfind><prop><displayname/></prop></propfind>",
        b'<?xml version="1.0" encoding="Shift_JIS"?><propfind xmlns="DAV:"/>',
        b'<?xml version="1.0" encoding="bogus"?><propfind xmlns="DAV:"/>',
        b'<!DOCTYPE propfind [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
        b'<propfind xmlns="DAV:"><prop><displayname>&b;</displayname></prop></propfind>',
    ],
)
def test_invalid_body(body):
    with pytest.raises(RequestException) as ex:
        _deserializer.deserialize(body)
    assert ex.value.error is err.ERROR_DAV_XML_INVALID
