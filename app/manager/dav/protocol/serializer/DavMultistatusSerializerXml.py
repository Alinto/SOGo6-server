from __future__ import annotations
from typing import TYPE_CHECKING

import re
from http import HTTPStatus
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

from app.manager.dav.protocol.DavProtocolConst import (
    DAV_HREF,
    DAV_MULTISTATUS,
    DAV_PROP,
    DAV_PROPSTAT,
    DAV_RESPONSE,
    DAV_STATUS,
    NS_PREFIXES,
)
from app.manager.dav.protocol.model.DavHrefs import DavHrefs
from app.manager.dav.protocol.model.DavMultistatus import DavMultistatus
from app.manager.dav.protocol.model.DavResourceType import DavResourceType
from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.manager.dav.protocol.model.DavPropResponse import DavPropResponse, DavPropValue

# ElementTree keeps its prefixes in a registry shared by the whole process. They are registered once, when the
# module is loaded: registering them at each serialization would change the registry under concurrent ones.
for _prefix, _namespace in NS_PREFIXES.items():
    register_namespace(_prefix, _namespace)


class DavMultistatusSerializerXml(Serializer[DavMultistatus, bytes]):
    """Write a multistatus body (RFC 4918 section 13): for each resource, the properties found in a 200
    propstat and the missing ones in a 404 propstat."""

    # Characters outside the Char production of XML 1.0 (section 2.2), which ElementTree writes as is
    _FORBIDDEN_CHARS: re.Pattern[str] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")

    def serialize(self, data: DavMultistatus) -> bytes:
        """Write the multistatus in UTF-8, with its XML declaration."""
        multistatus: Element = Element(DAV_MULTISTATUS)
        for response in data.responses:
            DavMultistatusSerializerXml._append_response(multistatus=multistatus, response=response)
        return tostring(multistatus, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _append_response(multistatus: Element, response: DavPropResponse) -> None:
        """Append the response of one resource, with a propstat per status."""
        node: Element = SubElement(multistatus, DAV_RESPONSE)
        SubElement(node, DAV_HREF).text = DavMultistatusSerializerXml._encode_href(response.href)
        # A response needs a propstat: a resource without any property gets an empty one
        if response.found or not response.missing:
            found: list[Element] = [
                DavMultistatusSerializerXml._write_prop(name=name, value=value)
                for name, value in response.found.items()
            ]
            DavMultistatusSerializerXml._append_propstat(node=node, props=found, status=HTTPStatus.OK)
        if response.missing:
            missing: list[Element] = [Element(name) for name in response.missing]
            DavMultistatusSerializerXml._append_propstat(node=node, props=missing, status=HTTPStatus.NOT_FOUND)

    @staticmethod
    def _write_prop(name: str, value: DavPropValue) -> Element:
        """Write a property element holding its value."""
        prop: Element = Element(name)
        if isinstance(value, DavHrefs):
            for href in value.hrefs:
                SubElement(prop, DAV_HREF).text = DavMultistatusSerializerXml._encode_href(href)
        elif isinstance(value, DavResourceType):
            for resource_type in value.types:
                SubElement(prop, resource_type)
        else:
            prop.text = DavMultistatusSerializerXml._FORBIDDEN_CHARS.sub("", value)
        return prop

    @staticmethod
    def _append_propstat(node: Element, props: list[Element], status: HTTPStatus) -> None:
        """Append to a response a propstat holding the properties and their status."""
        propstat: Element = SubElement(node, DAV_PROPSTAT)
        SubElement(propstat, DAV_PROP).extend(props)
        SubElement(propstat, DAV_STATUS).text = f"HTTP/1.1 {status.value} {status.phrase}"

    @staticmethod
    def _encode_href(path: str) -> str:
        """Percent-encode a path into a URI path (RFC 3986 section 3.3), keeping as is the characters a path
        segment allows: the "@" of the logins stays readable."""
        return quote(path, safe="/@:!$&'()*+,;=")
