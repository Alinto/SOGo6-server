from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar

from http import HTTPStatus

from app.dav.DavConst import DAV_COMPLIANCE_CLASSES, DAV_METHODS
from app.dav.handler.DavHandler import DavHandler
from app.dav.model.DavResponse import DavResponse

if TYPE_CHECKING:
    from app.dav.model.DavRequest import DavRequest


class DavOptionsHandler(DavHandler):
    """Answer OPTIONS with the DAV compliance classes and the methods the server handles.

    Clients send OPTIONS first to learn whether the server speaks WebDAV (RFC 4918 section 10.1),
    then CalDAV or CardDAV through the same header (RFC 4791 section 5.1, RFC 6352 section 6.1).
    """

    method: ClassVar[str] = "OPTIONS"

    def handle(self, request: DavRequest) -> DavResponse:
        """Return the DAV and Allow headers, without body."""
        headers: dict[str, str] = {
            "DAV": ", ".join(DAV_COMPLIANCE_CLASSES),
            "Allow": ", ".join(sorted(DAV_METHODS)),
        }
        return DavResponse(status=HTTPStatus.OK, headers=headers)
