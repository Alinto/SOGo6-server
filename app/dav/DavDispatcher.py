from __future__ import annotations
from typing import TYPE_CHECKING

import logging
from http import HTTPStatus

from app.dav.DavConst import DAV_AUTH_CHALLENGE, DAV_XML_CONTENT_TYPE
from app.dav.model.DavResponse import DavResponse
from app.manager.dav.protocol.DavProtocolConst import DAV_PROPFIND_FINITE_DEPTH
from app.manager.dav.protocol.model.DavError import DavError
from app.manager.dav.protocol.serializer.DavErrorSerializerXml import DavErrorSerializerXml
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_dav

if TYPE_CHECKING:
    from app.dav.handler.DavHandler import DavHandler
    from app.dav.model.DavRequest import DavRequest


class DavDispatcher:
    """Route a DAV request to the handler of its HTTP method.

    Every request is refused with 503 while SOGo has no configuration, so that clients retry later
    instead of dropping the account. The WSGI layer only lets through the methods of ``DAV_METHODS``,
    which all have a handler: a method without one is a wiring error, answered 501. A
    ``RequestException`` raised by a handler, authentication included, is turned into the HTTP status of
    its error, with an XML body naming the condition the request failed when the error has one (RFC 4918
    section 16); unexpected exceptions are left to the WSGI layer, which logs them.
    """

    # Condition named in the body of an error response, by error raised
    _CONDITIONS: dict[err.E, str] = {err.ERROR_DAV_PROPFIND_INFINITE_DEPTH: DAV_PROPFIND_FINITE_DEPTH}

    def __init__(self, handlers: list[DavHandler], sogo_state: int) -> None:
        self._handlers: dict[str, DavHandler] = {handler.method: handler for handler in handlers}
        self._sogo_state: int = sogo_state
        self._error_serializer: DavErrorSerializerXml = DavErrorSerializerXml()

    def dispatch(self, request: DavRequest) -> DavResponse:
        """Run the handler of the request method and return its response.

        A 401 always carries the Basic challenge, which this status requires (RFC 9110 section 15.5.2).
        """
        if self._sogo_state != cs.SOGO_OK:
            return DavResponse(status=HTTPStatus.SERVICE_UNAVAILABLE)
        handler: DavHandler | None = self._handlers.get(request.method)
        if handler is None:
            return DavResponse(status=HTTPStatus.NOT_IMPLEMENTED)
        try:
            return handler.handle(request)
        except RequestException as ex:
            status: HTTPStatus = HTTPStatus(ex.http_status)
            log_level: int = logging.WARNING
            if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
                log_level = logging.ERROR
            elif ex.error is err.ERROR_AUTHENTICATED_ROUTE:
                # Most clients send their first request without credentials and wait for the challenge
                log_level = logging.INFO
            logger_dav.log(log_level, "%s /%s failed: %s %s", request.method, request.path, ex.error.c, ex.error.m)
            if status == HTTPStatus.UNAUTHORIZED:
                return DavResponse(status=status, headers={"WWW-Authenticate": DAV_AUTH_CHALLENGE})
            condition: str | None = DavDispatcher._CONDITIONS.get(ex.error)
            if condition is None:
                return DavResponse(status=status)
            return DavResponse(
                status=status,
                headers={"Content-Type": DAV_XML_CONTENT_TYPE},
                body=self._error_serializer.serialize(DavError(condition=condition)),
            )
