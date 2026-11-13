"""Unit tests for DavApp - Flask test client, dispatcher mocked."""

from http import HTTPStatus
from unittest.mock import MagicMock

from app.dav.DavApp import DavApp
from app.dav.DavConst import DAV_METHODS
from app.dav.model.DavResponse import DavResponse


def _client(response=None, error=None):
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = response or DavResponse(status=HTTPStatus.OK)
    if error is not None:
        dispatcher.dispatch.side_effect = error
    return DavApp(dispatcher).create_flask_app().test_client(), dispatcher


# ========== Routing ==========


def test_request_converted_for_dispatcher():
    client, dispatcher = _client()
    client.open("/dav/alice%40example.org/Calendar/", method="OPTIONS", data=b"<body/>", headers={"Depth": "1"})
    request = dispatcher.dispatch.call_args.args[0]
    assert request.method == "OPTIONS"
    assert request.path == "alice@example.org/Calendar/"
    assert request.headers["depth"] == "1"
    assert request.body == b"<body/>"


def test_root_without_trailing_slash_not_redirected():
    client, dispatcher = _client()
    response = client.open("/dav", method="OPTIONS")
    assert response.status_code == HTTPStatus.OK
    assert dispatcher.dispatch.call_args.args[0].path == ""


def test_well_known_redirects_to_root():
    client, dispatcher = _client()
    for path in ("/.well-known/caldav", "/.well-known/carddav"):
        response = client.open(path, method="OPTIONS")
        assert response.status_code == HTTPStatus.MOVED_PERMANENTLY
        assert response.headers["Location"] == "/dav/"
        assert response.headers["Cache-Control"] == "no-cache"
        assert "Content-Type" not in response.headers
    dispatcher.dispatch.assert_not_called()


def test_response_converted_without_default_content_type():
    client, _ = _client(DavResponse(status=HTTPStatus.NO_CONTENT, headers={"ETag": '"1"'}))
    response = client.open("/dav/alice@example.org/", method="OPTIONS")
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.headers["ETag"] == '"1"'
    assert "Content-Type" not in response.headers


# ========== Errors ==========


def test_method_not_served_lists_allowed():
    client, dispatcher = _client()
    response = client.open("/dav/", method="PATCH")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert set(response.headers["Allow"].split(", ")) == DAV_METHODS
    assert response.data == b""
    dispatcher.dispatch.assert_not_called()


def test_unknown_path_empty_not_found():
    client, _ = _client()
    response = client.get("/")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.data == b""


def test_unexpected_exception_empty_server_error():
    client, _ = _client(error=RuntimeError("boom"))
    response = client.open("/dav/", method="OPTIONS")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.data == b""
