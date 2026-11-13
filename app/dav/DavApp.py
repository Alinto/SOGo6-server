from __future__ import annotations
from typing import TYPE_CHECKING

from http import HTTPStatus

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from app.dav.DavConst import DAV_METHODS, DAV_ROOT_PATH, WELL_KNOWN_CALDAV_PATH, WELL_KNOWN_CARDDAV_PATH
from app.dav.model.DavRequest import DavRequest
from app.utils import constants as cs

if TYPE_CHECKING:
    from app.dav.DavDispatcher import DavDispatcher
    from app.dav.model.DavResponse import DavResponse


class DavApp:
    """WSGI application of the DAV server, the only DAV file that depends on Flask.

    Flask is reduced to a catch-all route under the DAV root: each request is converted to a
    ``DavRequest``, handed to the dispatcher, and the ``DavResponse`` converted back. Three Flask
    behaviours meant for web applications are switched off because DAV clients trip on them:
    automatic OPTIONS answers (no DAV header), redirects on a missing trailing slash (clients address
    collections both ways) and HTML error pages.
    """

    def __init__(self, dispatcher: DavDispatcher) -> None:
        self._dispatcher: DavDispatcher = dispatcher

    def create_flask_app(self) -> Flask:
        """Create the Flask application and register the DAV routes on it."""
        app: Flask = Flask(__name__)
        app.config["MAX_CONTENT_LENGTH"] = cs.MAX_HTTP_REQUEST_BYTES
        app.url_map.strict_slashes = False
        app.add_url_rule(
            DAV_ROOT_PATH,
            endpoint="dav_root",
            view_func=self._serve,
            methods=DAV_METHODS,
            defaults={"path": ""},
            provide_automatic_options=False,
        )
        app.add_url_rule(
            f"{DAV_ROOT_PATH}<path:path>",
            endpoint="dav_path",
            view_func=self._serve,
            methods=DAV_METHODS,
            provide_automatic_options=False,
        )
        for endpoint, well_known_path in (
            ("well_known_caldav", WELL_KNOWN_CALDAV_PATH),
            ("well_known_carddav", WELL_KNOWN_CARDDAV_PATH),
        ):
            app.add_url_rule(
                well_known_path,
                endpoint=endpoint,
                view_func=DavApp._redirect_to_root,
                methods=DAV_METHODS,
                provide_automatic_options=False,
            )
        app.register_error_handler(MethodNotAllowed, DavApp._method_not_allowed)
        app.register_error_handler(HTTPException, DavApp._empty_error)
        return app

    def _serve(self, path: str) -> Response:
        """Convert the current Flask request, dispatch it and convert the response back."""
        dav_request: DavRequest = DavRequest(
            method=request.method,
            path=path,
            headers={name.lower(): value for name, value in request.headers.items()},
            body=request.get_data(),
        )
        dav_response: DavResponse = self._dispatcher.dispatch(dav_request)
        response: Response = Response(
            response=dav_response.body, status=dav_response.status, headers=dav_response.headers
        )
        if "Content-Type" not in dav_response.headers:
            # Flask always adds a default text/html type, wrong for an empty or binary DAV body.
            del response.headers["Content-Type"]
        return response

    @staticmethod
    def _redirect_to_root() -> Response:
        """Send a well-known URI to the DAV root, whatever the method (RFC 6764 section 5).

        A 301 is cached by default: the redirect is marked no-cache so that clients follow the DAV root
        if a deployment moves it.
        """
        return DavApp._bodyless(
            HTTPStatus.MOVED_PERMANENTLY, headers={"Location": DAV_ROOT_PATH, "Cache-Control": "no-cache"}
        )

    @staticmethod
    def _method_not_allowed(error: MethodNotAllowed) -> Response:
        """Answer 405 with the methods served, which this status requires (RFC 9110 section 15.5.6)."""
        return DavApp._bodyless(HTTPStatus.METHOD_NOT_ALLOWED, headers={"Allow": ", ".join(sorted(DAV_METHODS))})

    @staticmethod
    def _empty_error(error: HTTPException) -> Response:
        """Answer HTTP errors raised by Flask (unknown path, oversized body, crash) without the HTML
        page Flask renders by default. Flask has already logged unexpected exceptions."""
        return DavApp._bodyless(error.code or HTTPStatus.INTERNAL_SERVER_ERROR)

    @staticmethod
    def _bodyless(status: int, headers: dict[str, str] | None = None) -> Response:
        """Build a response without body, stripped of the text/html type Flask adds by default."""
        response: Response = Response(status=status, headers=headers)
        del response.headers["Content-Type"]
        return response
