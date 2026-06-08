from __future__ import annotations

from typing import Any

from flask import url_for


def build_external_url(endpoint: str, public_base_url: str, **values: Any) -> str:
    """Build an absolute URL for a Flask endpoint, preferring a configured public base URL.

    Behind a reverse proxy the host seen by Flask is not the public one, so when
    ``public_base_url`` is set the route path is prefixed with it; otherwise we fall back to
    Flask's own external URL (scheme + host as seen by the app).
    """
    path: str = url_for(endpoint, **values)
    if public_base_url:
        return public_base_url.rstrip("/") + path
    return url_for(endpoint, _external=True, **values)
