from __future__ import annotations
from typing import TYPE_CHECKING

from http import HTTPStatus

from app.dav.model.DavResponse import DavResponse
from app.utils import constants as cs
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
    ``RequestException`` raised by a handler is turned into the HTTP status of its error; unexpected
    exceptions are left to the WSGI layer, which logs them.
    """

    def __init__(self, handlers: list[DavHandler], sogo_state: int) -> None:
        self._handlers: dict[str, DavHandler] = {handler.method: handler for handler in handlers}
        self._sogo_state: int = sogo_state

    def dispatch(self, request: DavRequest) -> DavResponse:
        """Run the handler of the request method and return its response."""
        if self._sogo_state != cs.SOGO_OK:
            return DavResponse(status=HTTPStatus.SERVICE_UNAVAILABLE)
        handler: DavHandler | None = self._handlers.get(request.method)
        if handler is None:
            return DavResponse(status=HTTPStatus.NOT_IMPLEMENTED)
        try:
            return handler.handle(request)
        except RequestException as ex:
            logger_dav.error("%s /%s failed: %s %s", request.method, request.path, ex.error.c, ex.error.m)
            return DavResponse(status=HTTPStatus(ex.http_status))
