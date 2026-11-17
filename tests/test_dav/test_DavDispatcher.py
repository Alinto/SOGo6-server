"""Unit tests for DavDispatcher - handlers are fakes, no WSGI layer involved."""

from http import HTTPStatus
import logging

import pytest

from app.dav.DavConst import DAV_AUTH_CHALLENGE
from app.dav.DavDispatcher import DavDispatcher
from app.dav.model.DavRequest import DavRequest
from app.dav.model.DavResponse import DavResponse
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException


class FakePropfindHandler:
    def __init__(self, error=None):
        self.method = "PROPFIND"
        self.error = error
        self.calls = []

    def handle(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise RequestException(error=self.error)
        return DavResponse(status=HTTPStatus.MULTI_STATUS)


def _dispatch(handler, request, sogo_state=cs.SOGO_OK):
    return DavDispatcher(handlers=[handler], sogo_state=sogo_state).dispatch(request)


def test_dispatch_to_method_handler():
    handler = FakePropfindHandler()
    request = DavRequest(method="PROPFIND", path="alice@example.org/")
    assert _dispatch(handler, request).status == HTTPStatus.MULTI_STATUS
    assert handler.calls == [request]


def test_method_without_handler_not_implemented():
    response = _dispatch(FakePropfindHandler(), DavRequest(method="REPORT", path=""))
    assert response.status == HTTPStatus.NOT_IMPLEMENTED
    assert response.body == b""


def test_not_configured_unavailable():
    handler = FakePropfindHandler()
    response = _dispatch(handler, DavRequest(method="PROPFIND", path=""), sogo_state=cs.SOGO_NOT_INIT)
    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE
    assert not handler.calls


def test_request_exception_uses_error_status():
    handler = FakePropfindHandler(error=err.ERROR_SHARE_NOT_FOUND)
    response = _dispatch(handler, DavRequest(method="PROPFIND", path="bob@example.org/"))
    assert response.status == HTTPStatus.NOT_FOUND


def test_unauthorized_carries_challenge():
    handler = FakePropfindHandler(error=err.ERROR_LOGIN_FAILED)
    response = _dispatch(handler, DavRequest(method="PROPFIND", path=""))
    assert response.status == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == DAV_AUTH_CHALLENGE


def test_insecure_forbidden_without_challenge():
    handler = FakePropfindHandler(error=err.ERROR_DAV_INSECURE_CONNECTION)
    response = _dispatch(handler, DavRequest(method="PROPFIND", path=""))
    assert response.status == HTTPStatus.FORBIDDEN
    assert "WWW-Authenticate" not in response.headers


@pytest.mark.parametrize(
    "error, level",
    [
        (err.ERROR_AUTHENTICATED_ROUTE, logging.INFO),
        (err.ERROR_LOGIN_FAILED, logging.WARNING),
        (err.ERROR_UNKOWN, logging.ERROR),
    ],
)
def test_failure_log_level(caplog, error, level):
    caplog.set_level(logging.INFO, logger="sogolog.dav")
    _dispatch(FakePropfindHandler(error=error), DavRequest(method="PROPFIND", path=""))
    assert [record.levelno for record in caplog.records if record.name == "sogolog.dav"] == [level]
