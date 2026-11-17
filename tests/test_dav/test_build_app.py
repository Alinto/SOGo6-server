"""Unit tests for the DAV build_app - worker initialisation mocked."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from app.dav.DavConst import DAV_METHODS
from app.dav.build_app import build_app
from app.dav.handler.DavHandler import DavHandler
from app.utils import constants as cs


@pytest.fixture(autouse=True)
def cache():
    with patch("app.dav.handler.DavHandler.sogo_cache"):
        yield


def _build(sogo_state=cs.SOGO_OK):
    with (
        patch("app.dav.build_app.init_worker", return_value=(sogo_state, MagicMock(), MagicMock())),
        patch("app.dav.build_app.set_cache"),
        patch("app.dav.build_app.set_agent"),
    ):
        return build_app()


def test_one_handler_per_served_method():
    with patch("app.dav.build_app.DavDispatcher") as dispatcher_class:
        _build()
    handlers = dispatcher_class.call_args.kwargs["handlers"]
    assert sorted(handler.method for handler in handlers) == sorted(DAV_METHODS)


def test_handlers_keep_authentication():
    with patch("app.dav.build_app.DavDispatcher") as dispatcher_class:
        _build()
    handlers = dispatcher_class.call_args.kwargs["handlers"]
    assert all(type(handler).handle is DavHandler.handle for handler in handlers)


def test_options_answered_by_dav_handler():
    client = _build().test_client()
    with patch("app.dav.DavAuthenticator.DavAuthenticator.authenticate"):
        response = client.open("/dav/", method="OPTIONS")
    assert response.status_code == HTTPStatus.OK
    assert response.headers["DAV"] == "1"


def test_options_without_credentials_challenged():
    response = _build().test_client().open("/dav/", method="OPTIONS", base_url="https://localhost")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"].startswith("Basic realm=")


def test_not_configured_unavailable():
    response = _build(sogo_state=cs.SOGO_NOT_INIT).test_client().open("/dav/", method="OPTIONS")
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
