# -*- coding: utf-8 -*-
from json import loads, dumps
from json.decoder import JSONDecodeError


from flask import Flask, request, g, Response
from flask.typing import ResponseReturnValue
from flask_smorest import Api, Blueprint
from flask_cors import CORS
from flask_wtf import CSRFProtect

from marshmallow.exceptions import ValidationError

from app.config.settings.ProcessSetting import process_config
from app.config.init_config import init_get_system_and_default_settings
import app.utils.errors as err
from app.utils.api.ApiBaseResponse import create_api_base_response, ApiBaseResponse
from app.utils import cs_api

#Apis
from app.api import all_apis


__version__ = "6.0.0"

def create_app(sogo_state: int) -> Flask:
    """
    Create and configure the Flask application
    """
    app = Flask(__name__)
    app.config.from_object(process_config)

    # Don't work and do not set for dev env
    # CSRFProtect(app)

    if not app.config.get("DO_SWAGGER"):
        app.config.pop("BASIC_OPENAPI_URL_PREFIX")
        app.config.pop("ADMIN_OPENAPI_URL_PREFIX")


    flask_api = Api(app, config_prefix="BASIC_") # type: ignore [call-arg]
    admin_api = Api(app, config_prefix="ADMIN_") # type: ignore [call-arg]

    register_route(flask_api, cs_api.API_BASIC, sogo_state)
    register_route(admin_api, cs_api.API_ADMIN, sogo_state)

    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3001"}})

    return app


def register_before_request(base_blueprint: Blueprint, kind: str, sogo_state: int) -> None:
    """
    Add the different before request on tha api according to the kind and state

    :param base_blueprint: _description_
    :type base_blueprint: Blueprint
    :param name: _description_
    :type name: str
    :param sogo_state: _description_
    :type sogo_state: int
    :return: _description_
    :rtype: _type_
    """

    @base_blueprint.before_request
    def check_json_and_content_type() -> ResponseReturnValue | None:
        """
        Only accept request with json content when data is posting

        :return:app
        :rtype: ResponseReturnValue | None
        """
        if request.method in {"POST", "PATCH", "PUT"}:
            content_length = request.content_length
            if content_length is not None and content_length == 0:
                return None
            if not request.is_json:
                return create_api_base_response(error_code=err.ERROR_API_CONTENT_TYPE), 400
            data = request.get_data(as_text=True)
            try:
                loads(data)
            except (TypeError, JSONDecodeError):
                return create_api_base_response(error_code=err.ERROR_API_NOT_JSON), 400
        return None

    if sogo_state == cs_api.SOGO_NOT_INIT:
        if kind == cs_api.API_BASIC:
            @base_blueprint.before_request
            def block_sogo() -> ResponseReturnValue:
                """
                Reject requests for basic api id sogo is not init
                """
                return create_api_base_response(error_code=err.ERROR_SOGO_INIT), 412
        elif kind == cs_api.API_ADMIN:
            @base_blueprint.before_request
            def add_process() -> None:
                """
                _Add the process settings in g
                """
                if 'process' not in g:
                    g.process = process_config

    elif sogo_state == cs_api.SOGO_OK:
        @base_blueprint.before_request
        def get_config() -> None:
            """
            Get and set the config in the global flask
            """
            if 'process' not in g:
                g.process = process_config
            system_settings, default_domain_settings = init_get_system_and_default_settings()
            if 'system' not in g:
                g.system = system_settings
            if 'domain' not in g:
                g.default_domain = default_domain_settings


def register_after_request(base_blueprint: Blueprint) -> None:
    """
    register after request for the api

    :param base_blueprint: _description_
    :type base_blueprint: Blueprint
    :return: _description_
    :rtype: _type_
    """

    @base_blueprint.after_request
    def bad_request_handler(response: Response) -> ResponseReturnValue:
        if response.status_code == 400:
            if response.content_type == "application/json":
                body = response.get_json()
                #Check if the body is a SOGo one
                try:
                    ApiBaseResponse().load(body)
                except ValidationError:
                    response.set_data(dumps(
                        create_api_base_response(body, err.ERROR_VALIDATION_ERROR)
                    ))
        return response

def register_route(flask_api: Api, name: str, sogo_state: int) -> None:
    """
    Resgister all blueprints
    """
    base_blueprint = Blueprint(name, name, url_prefix='/api')

    register_after_request(base_blueprint)
    register_before_request(base_blueprint, name, sogo_state)

    for version, version_apis in all_apis.items():
        version_blueprint = Blueprint(version, version, url_prefix=f'{name}/{version}')
        basic_apis = version_apis[name]
        for api in basic_apis:
            version_blueprint.register_blueprint(api)
        base_blueprint.register_blueprint(version_blueprint)

    flask_api.register_blueprint(base_blueprint)
