from flask import Flask, request
from flask.typing import ResponseReturnValue
from flask_compress import Compress


from app import __version__
from app.config.init_config import init_worker
from app.api.create_app import create_app
from app.service import set_agent, set_cache

def build_app() -> Flask:
    """Build the app for both dev and prod launcher"""
    sogo_state, cache, agent_client = init_worker()
    set_cache(cache)
    set_agent(agent_client)

    app = create_app(sogo_state)
    Compress().init_app(app)

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

    return app
