from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from app.manager.dav.protocol.DavProtocolConst import DAV_ERROR
from app.manager.dav.protocol.model.DavError import DavError
from app.utils.serializer.Serializer import Serializer


class DavErrorSerializerXml(Serializer[DavError, bytes]):
    """Write the body of an error response (RFC 4918 section 16): an error element holding the condition the
    request failed, as an empty element."""

    def serialize(self, data: DavError) -> bytes:
        """Write the error in UTF-8, with its XML declaration."""
        error: Element = Element(DAV_ERROR)
        SubElement(error, data.condition)
        return tostring(error, encoding="utf-8", xml_declaration=True)
