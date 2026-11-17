from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.init_config import init_worker
from app.config.settings.ProcessSetting import process_config
from app.dav.DavApp import DavApp
from app.dav.DavAuthenticator import DavAuthenticator
from app.dav.DavDispatcher import DavDispatcher
from app.dav.handler.DavOptionsHandler import DavOptionsHandler
from app.service import set_agent, set_cache
from app.utils import constants as cs
from app.utils.logger.logger import logger_dav

if TYPE_CHECKING:
    from flask import Flask

    from app.dav.handler.DavHandler import DavHandler


def build_app(require_secure: bool = True) -> Flask:
    """Build the DAV app for both dev and prod launcher.

    The configuration state is read once per worker, like the REST API does: a SOGo configured after
    start-up needs a restart of the DAV server. Every method of ``DAV_METHODS`` needs its handler here.
    ``require_secure`` refuses Basic authentication without TLS; only the development server, which
    has no reverse proxy in front of it, turns it off.
    """
    sogo_state, cache, agent_client = init_worker()
    set_cache(cache)
    set_agent(agent_client)
    if sogo_state != cs.SOGO_OK:
        logger_dav.warning("SOGo is not configured yet, every DAV request will be answered 503")

    authenticator: DavAuthenticator = DavAuthenticator(process_config, require_secure=require_secure)
    handlers: list[DavHandler] = [DavOptionsHandler(authenticator=authenticator)]
    dispatcher: DavDispatcher = DavDispatcher(handlers=handlers, sogo_state=sogo_state)
    return DavApp(dispatcher).create_flask_app()
