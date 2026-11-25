from __future__ import annotations
from typing import TYPE_CHECKING

from http import HTTPStatus

from app.dav.DavConst import DAV_XML_CONTENT_TYPE
from app.dav.handler.DavHandler import DavHandler
from app.dav.model.DavResponse import DavResponse
from app.dav.resource.DavResourceResolver import DavResourceResolver
from app.manager.dav.protocol.DavProtocolConst import DAV_ALLPROP_PROPERTIES
from app.manager.dav.protocol.model.DavMultistatus import DavMultistatus
from app.manager.dav.protocol.model.DavPropResponse import DavPropResponse
from app.manager.dav.protocol.model.enums.PropfindKind import PropfindKind
from app.manager.dav.protocol.serializer.DavMultistatusSerializerXml import DavMultistatusSerializerXml
from app.manager.dav.protocol.serializer.PropfindRequestDeserializerXml import PropfindRequestDeserializerXml
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.dav.DavAuthenticator import DavAuthenticator
    from app.dav.model.DavContext import DavContext
    from app.dav.model.DavRequest import DavRequest
    from app.dav.resource.DavResource import DavResource
    from app.manager.dav.protocol.model.DavPropResponse import DavPropValue
    from app.manager.dav.protocol.model.PropfindRequest import PropfindRequest


class DavPropfindHandler(DavHandler):
    """Answer PROPFIND with the properties of the resource of the path and, with Depth 1, of its members
    (RFC 4918 section 9.1).

    Depth infinity, which a request without Depth stands for, is refused as RFC 4918 section 9.1.1 allows: it
    would read every calendar and address book of the account.
    """

    # Depth values served, and the one refused (RFC 4918 section 10.2), whose case is ignored as in any
    # quoted string of the HTTP grammar
    _DEPTHS: tuple[str, ...] = ("0", "1")
    _DEPTH_INFINITY: str = "infinity"

    def __init__(self, authenticator: DavAuthenticator) -> None:
        super().__init__(method="PROPFIND", authenticator=authenticator)
        self._deserializer: PropfindRequestDeserializerXml = PropfindRequestDeserializerXml()
        self._serializer: DavMultistatusSerializerXml = DavMultistatusSerializerXml()

    def process(self, request: DavRequest, context: DavContext) -> DavResponse:
        """
        Return the multistatus of the properties asked.

        :param request: The PROPFIND request
        :type request: DavRequest
        :param context: The context of the request
        :type context: DavContext
        :raises RequestException: ERROR_DAV_PROPFIND_INFINITE_DEPTH for Depth infinity or without Depth,
            ERROR_DAV_DEPTH_INVALID for a Depth other than 0, 1 or infinity, ERROR_DAV_XML_INVALID for an invalid
            body, ERROR_DAV_RESOURCE_NOT_FOUND for an unknown path
        :return: The 207 response
        :rtype: DavResponse
        """
        depth: str | None = request.headers.get("depth")
        if depth is None or depth.lower() == DavPropfindHandler._DEPTH_INFINITY:
            raise RequestException(error=err.ERROR_DAV_PROPFIND_INFINITE_DEPTH)
        if depth not in DavPropfindHandler._DEPTHS:
            raise RequestException(error=err.ERROR_DAV_DEPTH_INVALID)
        propfind: PropfindRequest = self._deserializer.deserialize(request.body)
        resource: DavResource = DavResourceResolver.resolve(path=request.path, context=context)
        resources: list[DavResource] = [resource]
        if depth == "1":
            resources.extend(resource.children())
        multistatus: DavMultistatus = DavMultistatus(
            responses=tuple(
                DavPropfindHandler._prop_response(resource=member, propfind=propfind) for member in resources
            )
        )
        return DavResponse(
            status=HTTPStatus.MULTI_STATUS,
            headers={"Content-Type": DAV_XML_CONTENT_TYPE},
            body=self._serializer.serialize(multistatus),
        )

    @staticmethod
    def _prop_response(resource: DavResource, propfind: PropfindRequest) -> DavPropResponse:
        """Return the properties of a resource asked by a PROPFIND: the names alone for a propname, the WebDAV
        properties and the included ones for an allprop."""
        properties: dict[str, DavPropValue] = resource.properties()
        if propfind.kind is PropfindKind.PROPNAME:
            # The names are written as empty elements
            names: dict[str, DavPropValue] = {name: "" for name in properties}
            return DavPropResponse(href=resource.path, found=names)
        asked: tuple[str, ...] = propfind.props
        if propfind.kind is PropfindKind.ALLPROP:
            asked = tuple(name for name in properties if name in DAV_ALLPROP_PROPERTIES) + asked
        # A property shows up once in a response, even when asked twice (RFC 4918 section 9.1)
        unique: tuple[str, ...] = tuple(dict.fromkeys(asked))
        return DavPropResponse(
            href=resource.path,
            found={name: properties[name] for name in unique if name in properties},
            missing=tuple(name for name in unique if name not in properties),
        )
