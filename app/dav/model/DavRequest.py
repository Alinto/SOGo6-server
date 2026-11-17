from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DavRequest:
    """HTTP request as seen by the DAV handlers, independent of the WSGI framework.

    ``path`` is relative to the DAV root and already percent-decoded (``alice%40example.org`` arrives
    as ``alice@example.org``). Header names are lowercase. ``secure`` is true when the client reached
    the server over TLS, directly or through a trusted reverse proxy.
    """

    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    secure: bool = False
