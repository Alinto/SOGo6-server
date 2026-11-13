from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus


@dataclass(frozen=True)
class DavResponse:
    """HTTP response built by the DAV handlers, converted to a WSGI response by ``DavApp``.

    An empty body is sent without any Content-Type: a handler returning content sets it itself.
    """

    status: HTTPStatus
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
