from __future__ import annotations
from typing import TYPE_CHECKING

from json import loads, dumps
from json.decoder import JSONDecodeError


from flask import Flask, request, g, Response, current_app
from flask.typing import ResponseReturnValue
from flask_smorest import Api, Blueprint
from flask_cors import CORS

from marshmallow.exceptions import ValidationError

from app.auth.User import User, UserAnonymous
from app.auth.service.VoucherUserService import VoucherUserService
from app.config.settings.ProcessSetting import process_config
from app.config.settings.SystemSettings import SystemSettingsObj
from app.config.init_config import init_get_system_and_default_settings
import app.utils.errors as err
from app.utils.api.ApiBaseResponse import create_api_base_response, ApiBaseResponse
from app.utils import constants as cs
from app.utils.logger.logger import logger
from app.utils.exceptions import AggravatedException

#Apis
from app.api import all_apis



__version__ = "6.0.0"


def create_app(sogo_state: int) -> Flask:
    """
    Create and configure the Flask application
    """
    app = Flask(__name__)
    app.config.from_object(process_config)

    if not app.config.get("DO_SWAGGER"):
        app.config.pop("BASIC_OPENAPI_URL_PREFIX")
        app.config.pop("ADMIN_OPENAPI_URL_PREFIX")


    flask_api = Api(app, config_prefix="BASIC_") # type: ignore [call-arg]
    admin_api = Api(app, config_prefix="ADMIN_") # type: ignore [call-arg]

    register_route(flask_api, cs.API_BASIC, sogo_state)
    register_route(admin_api, cs.API_ADMIN, sogo_state)

    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

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
                return create_api_base_response(error=err.ERROR_API_CONTENT_TYPE), 400
            data = request.get_data(as_text=True)
            try:
                loads(data)
            except (TypeError, JSONDecodeError):
                return create_api_base_response(error=err.ERROR_API_NOT_JSON), 400
        return None

    @base_blueprint.before_request
    def get_user() -> ResponseReturnValue | None:
        """
        Add the user instance, even if there is no user
        """

        auth_header = request.authorization
        user: User = UserAnonymous()
        if auth_header:
            if auth_header.type == 'bearer':
                user = VoucherUserService(process_config).generate_user_from_voucher(auth_header.token)
            elif auth_header.type == 'basic' and current_app.config[cs.ALLOW_AUTH_BASIC]:
                pass
            else:
                return create_api_base_response(error=err.ERROR_WRONG_AUTHORIZATION_TYPE), 400
        g.user = user
        #TODO check login? with interval?
        return None

    if kind == cs.API_BASIC:
        @base_blueprint.before_request
        def check_non_anonymous_endpoint() -> ResponseReturnValue | None:
            """
            Add the user instance, even if there is no user
            """
            anon_endpoints = {
                "user#Auth.v1_Auth.Auth.ApiAuthUserMode", 
                "user#Auth.v1_Auth.Auth.ApiAuthUserLogin",
                "user#Auth.v1_Auth.Auth.ApiAuthUserCallback",
                "user#System.v1_System.System.ApiSystem",
            }
            if isinstance(g.user, UserAnonymous) and request.endpoint not in anon_endpoints:
                return create_api_base_response(error=err.ERROR_AUTHENTICATED_ROUTE), 401
            return None

    if sogo_state == cs.SOGO_NOT_INIT:
        if kind == cs.API_BASIC:
            @base_blueprint.before_request
            def block_sogo() -> ResponseReturnValue:
                """
                Reject requests for basic api id sogo is not init
                """
                return create_api_base_response(error=err.ERROR_SOGO_INIT), 412
        elif kind == cs.API_ADMIN:
            @base_blueprint.before_request
            def add_process() -> None:
                """
                _Add the process settings in g
                """
                if 'process' not in g:
                    g.process_settings = process_config

    elif sogo_state == cs.SOGO_OK:
        @base_blueprint.before_request
        def get_config() -> None:
            """
            Get and set the config in the global flask
            """
            if 'process' not in g:
                g.process_settings = process_config
            system_settings, default_domain_settings = init_get_system_and_default_settings()
            if 'system_settings' not in g:
                g.system_settings = system_settings
            if 'default_domain' not in g:
                g.default_domain_settings = default_domain_settings
            if 'user' in g:
                #TODO retreive domain settings relative to user domain here (for now just get default)
                g.user_domain_settings = default_domain_settings
            else:
                logger.error("No user in Flask g")
                raise AggravatedException("No user in Flask g")


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
    # base_blueprint = Blueprint(f"{name}_banane", name, url_prefix='/api')

    # register_after_request(base_blueprint)
    # register_before_request(base_blueprint, name, sogo_state)

    for version, version_apis in all_apis.items():
        basic_apis = version_apis[name]
        for api in basic_apis:
            version_blueprint = Blueprint(f"{version}_{api.name}", version, url_prefix=f'{name}/{version}')
            version_blueprint.register_blueprint(api)
            base_blueprint = Blueprint(f"{name}#{api.name}", name, url_prefix='/api')
            base_blueprint.register_blueprint(version_blueprint)
            register_after_request(base_blueprint)
            register_before_request(base_blueprint, name, sogo_state)

            flask_api.register_blueprint(base_blueprint)
