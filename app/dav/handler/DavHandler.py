from __future__ import annotations
from typing import TYPE_CHECKING, final

from abc import ABC, abstractmethod
from contextlib import closing

from app.service import sogo_cache

if TYPE_CHECKING:
    from app.dav.DavAuthenticator import DavAuthenticator
    from app.dav.model.DavContext import DavContext
    from app.dav.model.DavRequest import DavRequest
    from app.dav.model.DavResponse import DavResponse


class DavHandler(ABC):
    """Handles one HTTP method, whatever the DAV resource targeted.

    The dispatcher routes on ``method``. ``handle`` authenticates the request before ``process``, which
    cannot run without it; resolving the targeted resource is the job of ``process``.
    """

    def __init__(self, method: str, authenticator: DavAuthenticator) -> None:
        self.method: str = method
        self._authenticator: DavAuthenticator = authenticator

    @final
    def handle(self, request: DavRequest) -> DavResponse:
        """Authenticate the request, then process it.

        The request gets its own cache client, shared by the authentication and the processing through
        the context, and closed once the response is built, even on errors.

        :raises RequestException: when the authentication or the operation fails; the dispatcher
            answers with the HTTP status carried by the error
        """
        with closing(sogo_cache()) as cache:
            context: DavContext = self._authenticator.authenticate(request, cache)
            return self.process(request, context)

    @abstractmethod
    def process(self, request: DavRequest, context: DavContext) -> DavResponse:
        """Process the authenticated request and build its response.

        :raises RequestException: when the operation fails
        """
