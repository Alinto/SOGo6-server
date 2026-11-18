from __future__ import annotations

from xml.etree.ElementTree import Element, ParseError, TreeBuilder, XMLParser

from app.manager.dav.protocol.DavProtocolConst import (
    DAV_ALLPROP,
    DAV_INCLUDE,
    DAV_PROP,
    DAV_PROPFIND,
    DAV_PROPNAME,
)
from app.manager.dav.protocol.model.enums.PropfindKind import PropfindKind
from app.manager.dav.protocol.model.PropfindRequest import PropfindRequest
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_dav
from app.utils.serializer.Deserializer import Deserializer


class _DoctypeRefusingBuilder(TreeBuilder):
    """Tree builder refusing a document type declaration, and so the entities it defines."""

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        """Refuse the document type declaration."""
        raise RequestException(error=err.ERROR_DAV_XML_INVALID)


class PropfindRequestDeserializerXml(Deserializer[bytes, PropfindRequest]):
    """Read the body of a PROPFIND request (RFC 4918 section 9.1).

    A body declaring a document type is refused. Unknown elements are ignored, as WebDAV requires for its
    extensions (RFC 4918 section 17).
    """

    # Small enough to stop early on a refused body, without slowing down the parse of a valid one
    _FEED_CHUNK_BYTES: int = 4096

    def deserialize(self, data: bytes) -> PropfindRequest:
        """
        Read the properties asked by a PROPFIND request.

        :param data: The request body, empty for all the properties
        :type data: bytes
        :raises RequestException: ERROR_DAV_XML_INVALID when the body is not a propfind element asking for
            allprop, propname or prop
        :return: The properties asked
        :rtype: PropfindRequest
        """
        if not data.strip():
            return PropfindRequest(kind=PropfindKind.ALLPROP)
        root: Element = PropfindRequestDeserializerXml._parse(data)
        if root.tag != DAV_PROPFIND:
            raise RequestException(error=err.ERROR_DAV_XML_INVALID)
        for child in root:
            if child.tag == DAV_PROP:
                return PropfindRequest(kind=PropfindKind.PROP, props=tuple(prop.tag for prop in child))
            if child.tag == DAV_PROPNAME:
                return PropfindRequest(kind=PropfindKind.PROPNAME)
            if child.tag == DAV_ALLPROP:
                include: Element | None = root.find(DAV_INCLUDE)
                included: tuple[str, ...] = tuple(prop.tag for prop in include) if include is not None else ()
                return PropfindRequest(kind=PropfindKind.ALLPROP, props=included)
        raise RequestException(error=err.ERROR_DAV_XML_INVALID)

    @staticmethod
    def _parse(body: bytes) -> Element:
        """Parse a request body, refusing a document type declaration.

        Expat raises the refusal only once it has processed all the data it was given, entities included. The
        body is given by chunks, so that the parse stops at the end of the chunk holding the declaration: the
        expansion of the entities of that chunk is bounded by expat.
        """
        chunk: int = PropfindRequestDeserializerXml._FEED_CHUNK_BYTES
        parser: XMLParser = XMLParser(target=_DoctypeRefusingBuilder())
        try:
            for start in range(0, len(body), chunk):
                parser.feed(body[start : start + chunk])
            root: Element = parser.close()
        except (ParseError, ValueError, LookupError) as ex:
            # ValueError and LookupError: an encoding expat does not support, or an unknown one
            logger_dav.warning("Invalid DAV XML body: %s", ex)
            raise RequestException(error=err.ERROR_DAV_XML_INVALID) from ex
        return root
