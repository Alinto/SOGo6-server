# -*- coding: utf-8 -*-

from flask import Flask
from flask_smorest import Api, Blueprint
from app.config_sogo import config

#Apis
from app.preferences import pref_apis


__version__ = "6.0.0"

def create_app():
    """
    Create and configure the Flask application
    """
    app = Flask(__name__)
    app.config.from_object(config)

    app.config["API_TITLE"] = "My API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config['OPENAPI_URL_PREFIX'] = "/"
    app.config['OPENAPI_SWAGGER_UI_PATH'] = "/swagger-ui"
    app.config['OPENAPI_SWAGGER_UI_URL'] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    flask_api = Api(app)

    register_routes(flask_api)

    return app

def register_routes(flask_api: Api):
    """
    Resgister all blueprints
    """
    base_blueprint = Blueprint('base', 'base', url_prefix='/api')

    for api in pref_apis:
        base_blueprint.register_blueprint(api)
    
    flask_api.register_blueprint(base_blueprint)
