"""Unit tests for the DAV build_app - worker initialisation mocked."""

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.auth.User import User
from app.dav.DavConst import DAV_METHODS
from app.dav.build_app import build_app
from app.dav.handler.DavHandler import DavHandler
from app.dav.model.DavContext import DavContext
from app.utils import constants as cs

CONTEXT = DavContext(
    process_settings=SimpleNamespace(),
    system_settings={},
    user_domain_settings={},
    user=User("alice@example.org", "secret"),
    cache=SimpleNamespace(),
    account_alias=None,
)


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


def test_propfind_answered_with_multistatus():
    client = _build().test_client()
    with patch("app.dav.DavAuthenticator.DavAuthenticator.authenticate", return_value=CONTEXT):
        response = client.open(
            "/dav/",
            method="PROPFIND",
            headers={"Depth": "0"},
            data=b'<D:propfind xmlns:D="DAV:"><D:prop><D:current-user-principal/></D:prop></D:propfind>',
        )
    assert response.status_code == HTTPStatus.MULTI_STATUS
    assert response.headers["Content-Type"] == "application/xml; charset=utf-8"
    assert b"<D:current-user-principal><D:href>/dav/alice@example.org/</D:href>" in response.data


def test_propfind_without_depth_error_body():
    client = _build().test_client()
    with patch("app.dav.DavAuthenticator.DavAuthenticator.authenticate", return_value=CONTEXT):
        response = client.open("/dav/", method="PROPFIND")
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.data.endswith(b'<D:error xmlns:D="DAV:"><D:propfind-finite-depth /></D:error>')


def test_options_without_credentials_challenged():
    response = _build().test_client().open("/dav/", method="OPTIONS", base_url="https://localhost")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"].startswith("Basic realm=")


def test_not_configured_unavailable():
    response = _build(sogo_state=cs.SOGO_NOT_INIT).test_client().open("/dav/", method="OPTIONS")
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
