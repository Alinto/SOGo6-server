from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass

if TYPE_CHECKING:
    from app.manager.dav.protocol.model.DavPropResponse import DavPropResponse


@dataclass(frozen=True)
class DavMultistatus:
    """Multistatus response (RFC 4918 section 13): the properties of each resource."""

    responses: tuple[DavPropResponse, ...] = ()
