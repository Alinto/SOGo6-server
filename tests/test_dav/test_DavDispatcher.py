"""Unit tests for DavDispatcher - handlers are fakes, no WSGI layer involved."""

from http import HTTPStatus
from typing import ClassVar

from app.dav.DavDispatcher import DavDispatcher
from app.dav.handler.DavHandler import DavHandler
from app.dav.model.DavRequest import DavRequest
from app.dav.model.DavResponse import DavResponse
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException


class FakePropfindHandler(DavHandler):
    method: ClassVar[str] = "PROPFIND"

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def handle(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise RequestException(error=self.error)
        return DavResponse(status=HTTPStatus.MULTI_STATUS)


def test_dispatch_to_method_handler():
    handler = FakePropfindHandler()
    dispatcher = DavDispatcher(handlers=[handler], sogo_state=cs.SOGO_OK)
    request = DavRequest(method="PROPFIND", path="alice@example.org/")
    assert dispatcher.dispatch(request).status == HTTPStatus.MULTI_STATUS
    assert handler.calls == [request]


def test_method_without_handler_not_implemented():
    dispatcher = DavDispatcher(handlers=[FakePropfindHandler()], sogo_state=cs.SOGO_OK)
    response = dispatcher.dispatch(DavRequest(method="REPORT", path=""))
    assert response.status == HTTPStatus.NOT_IMPLEMENTED
    assert response.body == b""


def test_not_configured_unavailable():
    handler = FakePropfindHandler()
    dispatcher = DavDispatcher(handlers=[handler], sogo_state=cs.SOGO_NOT_INIT)
    response = dispatcher.dispatch(DavRequest(method="PROPFIND", path=""))
    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE
    assert not handler.calls


def test_request_exception_uses_error_status():
    handler = FakePropfindHandler(error=err.ERROR_SHARE_NOT_FOUND)
    dispatcher = DavDispatcher(handlers=[handler], sogo_state=cs.SOGO_OK)
    response = dispatcher.dispatch(DavRequest(method="PROPFIND", path="bob@example.org/"))
    assert response.status == HTTPStatus.NOT_FOUND
