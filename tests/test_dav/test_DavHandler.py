"""Unit tests for DavHandler - the authenticator and the cache client are fakes."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from app.dav.handler.DavHandler import DavHandler
from app.dav.model.DavRequest import DavRequest
from app.dav.model.DavResponse import DavResponse
from app.utils import errors as err
from app.utils.exceptions import RequestException


class FakeCache:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeAuthenticator:
    def __init__(self, error=None):
        self.error = error
        self.caches = []

    def authenticate(self, request, cache):
        self.caches.append(cache)
        if self.error is not None:
            raise RequestException(error=self.error)
        return "alice context"


class FakePropfindHandler(DavHandler):
    def __init__(self, authenticator, error=None):
        super().__init__(method="PROPFIND", authenticator=authenticator)
        self.error = error
        self.calls = []

    def process(self, request, context):
        self.calls.append((request, context))
        if self.error is not None:
            raise RequestException(error=self.error)
        return DavResponse(status=HTTPStatus.MULTI_STATUS)


@pytest.fixture
def cache():
    fake = FakeCache()
    with patch("app.dav.handler.DavHandler.sogo_cache", return_value=fake):
        yield fake


def _request():
    return DavRequest(method="PROPFIND", path="alice@example.org/")


def test_process_with_authenticated_context(cache):
    authenticator = FakeAuthenticator()
    handler = FakePropfindHandler(authenticator)
    request = _request()
    assert handler.handle(request).status == HTTPStatus.MULTI_STATUS
    assert handler.calls == [(request, "alice context")]
    assert authenticator.caches == [cache]
    assert cache.closed


def test_refused_authentication_not_processed(cache):
    handler = FakePropfindHandler(FakeAuthenticator(error=err.ERROR_LOGIN_FAILED))
    with pytest.raises(RequestException) as ex:
        handler.handle(_request())
    assert ex.value.error is err.ERROR_LOGIN_FAILED
    assert not handler.calls
    assert cache.closed


def test_cache_closed_when_process_fails(cache):
    handler = FakePropfindHandler(FakeAuthenticator(), error=err.ERROR_UNKOWN)
    with pytest.raises(RequestException):
        handler.handle(_request())
    assert cache.closed
