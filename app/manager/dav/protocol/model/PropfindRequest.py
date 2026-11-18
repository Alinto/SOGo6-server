from __future__ import annotations

from dataclasses import dataclass

from app.manager.dav.protocol.model.enums.PropfindKind import PropfindKind


@dataclass(frozen=True)
class PropfindRequest:
    """Properties asked by a PROPFIND request.

    ``props`` holds the names, in Clark notation, of the properties listed by a prop element, or of the
    extra properties listed by the include element of an allprop.
    """

    kind: PropfindKind
    props: tuple[str, ...] = ()
