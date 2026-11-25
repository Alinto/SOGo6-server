from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DavError:
    """Body of an error response (RFC 4918 section 16): the precondition or postcondition the request failed.

    ``condition`` is the name, in Clark notation, of the element of the condition, as
    "{DAV:}propfind-finite-depth".
    """

    condition: str
