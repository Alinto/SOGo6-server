from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar

from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from app.dav.model.DavRequest import DavRequest
    from app.dav.model.DavResponse import DavResponse


class DavHandler(ABC):
    """Handles one HTTP method, whatever the DAV resource targeted.

    The dispatcher routes on ``method``; resolving the targeted resource is the handler's job.
    """

    method: ClassVar[str]

    @abstractmethod
    def handle(self, request: DavRequest) -> DavResponse:
        """Process the request and build its response.

        :raises RequestException: when the operation fails; the dispatcher answers with the HTTP
            status carried by the error
        """
