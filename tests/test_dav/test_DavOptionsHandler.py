"""Unit tests for DavOptionsHandler."""

from http import HTTPStatus
from unittest.mock import patch

from app.dav.handler.DavOptionsHandler import DavOptionsHandler
from app.dav.model.DavRequest import DavRequest


def test_options_headers():
    with patch("app.dav.handler.DavOptionsHandler.DAV_METHODS", frozenset({"PROPFIND", "OPTIONS"})):
        response = DavOptionsHandler(authenticator=None).process(DavRequest(method="OPTIONS", path=""), context=None)
    assert response.status == HTTPStatus.OK
    assert response.headers["DAV"] == "1"
    assert response.headers["Allow"] == "OPTIONS, PROPFIND"
    assert response.body == b""
