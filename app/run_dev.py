from __future__ import annotations
from typing import TYPE_CHECKING

import os

import click
from flask_compress import Compress
from flask import request
from flask.typing import ResponseReturnValue
import logging



from app.api.create_app import create_app
from app.build_app import build_app
from app.config.init_config import init_once
from app.utils import constants as cs
from app.utils.logger.logger import logger

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis
    from app.manager.agent.ClientAgent import ClientAgent

#Beware that all methods called here will be called twice because the auto-reloader is on
#To see the correct behavior run:
#poetry run start --no-debug

@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default="5000")
@click.option("--debug/--no-debug", default=True)
@click.option("--ssl", is_flag=True)
@click.option("--auth", multiple=True)
def main(host: str, port: int, debug: bool, ssl: bool, auth: tuple[str]) -> None:
    """
    Main function starting the Flask application with passed arguments.
    """
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        init_once()

    app = build_app()

    ssl_context = "adhoc" if ssl else None

    #Look if we allow basic auth and unauthenticated request for debug
    if debug:
        logger.warning("SOGo is in debug mode")
        for mech in auth:
            if mech.lower() == "basic":
                app.config[cs.ALLOW_AUTH_BASIC] = True
                logger.warning("SOGo is in debug mode and allow basic auth")
            elif mech.lower() == "none":
                app.config[cs.ALLOW_AUTH_NO_CHECK] = True
                logger.warning("SOGo is in debug mode and will not check the password given")

    # List of arguments -> https://werkzeug.palletsprojects.com/en/stable/serving/#werkzeug.serving.run_simple
    app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)
