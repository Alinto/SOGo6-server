# -*- coding: utf-8 -*-

from flask import Flask
from flask_smorest import Api, Blueprint
from flask_wtf import CSRFProtect
from app.config.settings.ProcessSetting import process_config

#Apis
from app.api.preference import pref_apis
from app.api.admin import admin_apis
from app.api.mail import mail_apis


__version__ = "6.0.0"

def create_app() -> Flask:
    """
    Create and configure the Flask application
    """
    app = Flask(__name__)
    app.config.from_object(process_config)

    # Don't work and do not set for dev env
    # CSRFProtect(app)

    if not app.config.get("DO_SWAGGER"):
        app.config.pop("UI_OPENAPI_URL_PREFIX")
        app.config.pop("ADMIN_OPENAPI_URL_PREFIX")


    flask_api = Api(app, config_prefix="UI_")
    admin_api = Api(app, config_prefix="ADMIN_")

    register_route(flask_api)
    register_route_admin(admin_api)

    return app


def register_route(flask_api: Api):
    """
    Resgister all blueprints
    """
    base_ui_blueprint = Blueprint('ui_base', 'ui_base', url_prefix='/api')

    for api in mail_apis:
        base_ui_blueprint.register_blueprint(api)
    for api in pref_apis:
        base_ui_blueprint.register_blueprint(api)

    flask_api.register_blueprint(base_ui_blueprint)

def register_route_admin(admin_api: Api):
    """
    Resgister all blueprints for admin api
    """

    base_admin_blueprint = Blueprint('admin_base', 'admin_base', url_prefix='/api')

    for api in admin_apis:
        base_admin_blueprint.register_blueprint(api)

    admin_api.register_blueprint(base_admin_blueprint)
