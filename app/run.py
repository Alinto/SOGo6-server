from __future__ import annotations
from typing import TYPE_CHECKING

import click
from flask_compress import Compress
from flask import request
from flask.typing import ResponseReturnValue


from app import create_app, __version__
from app.config.init_config import init_sogo
from app.service import set_agent, set_cache
from app.utils import constants as cs
from app.utils.logger.logger import logger

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis

#Beware that all methods called here will be called twice because the auto-reloader is on
#To see the correct behavior run:
#poetry run start --no-debug

sogo_state, cache, agent_client = init_sogo()
set_cache(cache)
set_agent(agent_client)
app = create_app(sogo_state)


@app.route("/")
def index() -> ResponseReturnValue:
    """
    Simple index, return the state, version of the backend api and link to the swagger
    """
    if app.config["DO_SWAGGER"]:
        ret = {
            "state": sogo_state,
            "version": __version__,
            "swagger-sogo": request.base_url+app.config["BASIC_OPENAPI_SWAGGER_UI_PATH"][1:],
            "swagger-admin": request.base_url+app.config["ADMIN_OPENAPI_SWAGGER_UI_PATH"][1:]
        }
    else:
        ret = {
            "state": sogo_state,
            "version": __version__,
            "swagger-sogo": "not deployed",
            "swagger-admin": "not deployed"
        }
    return ret


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

    # enable automatic request compression
    compress = Compress()
    compress.init_app(app)

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


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
