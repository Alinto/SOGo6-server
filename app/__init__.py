from __future__ import annotations
from typing import TYPE_CHECKING, cast

from json import loads, dumps
from json.decoder import JSONDecodeError

from flask import Flask, request, g, Response, current_app
from flask.typing import ResponseReturnValue
from flask_smorest import Api, Blueprint
from flask_cors import CORS

from marshmallow.exceptions import ValidationError

from app.auth.User import User, UserAnonymous
from app.auth.Admin import Admin, AdminAnonymous
from app.auth.service.VoucherUserService import VoucherUserService
from app.auth.service.VoucherAdminService import VoucherAdminService
from app.config.settings.ProcessSetting import process_config
from app.config.settings.SystemSettings import SystemSettingsObj
from app.config.init_config import init_get_system_and_default_domain_settings, init_get_user_domain_settings
import app.utils.errors as err
from app.utils.api.ApiBaseResponse import create_api_base_response, ApiBaseResponse
from app.utils import constants as cs
from app.utils.logger.logger import logger, logger_api
from app.utils.exceptions import AggravatedException

#Apis
from app.api import all_apis
from app.interface.auth.InterfaceAuthUser import InterfaceAuthUser


__version__ = "6.0.alpha"


def create_app(sogo_state: int) -> Flask:
    """
    Create and configure the Flask application
    """
    app = Flask(__name__)
    app.config.from_object(process_config)
    # Hard cap on HTTP request body size, applied at the WSGI layer (Werkzeug). Protects
    # the server from oversized uploads before any application code reads the body into
    # memory. See app.utils.constants.MAX_HTTP_REQUEST_BYTES for the rationale.
    app.config["MAX_CONTENT_LENGTH"] = cs.MAX_HTTP_REQUEST_BYTES

    if not app.config.get("DO_SWAGGER"):
        app.config.pop("BASIC_OPENAPI_URL_PREFIX")
        app.config.pop("ADMIN_OPENAPI_URL_PREFIX")


    flask_api = Api(app, config_prefix="BASIC_") # type: ignore [call-arg]
    admin_api = Api(app, config_prefix="ADMIN_") # type: ignore [call-arg]

    register_route(flask_api, cs.API_BASIC, sogo_state)
    register_route(admin_api, cs.API_ADMIN, sogo_state)

    CORS(app, resources={r"/api/*": {"origins": "*",
                                     "allow_headers": ["authorization", "content-type"],
                                        "expose_headers": ["X-Pagination"]}})
    #TODO: remove CORS policy when we have a proper frontend

    return app


def _accepted_content_types() -> set[str] | None:
    """Return the per-route Content-Type allowlist, or None when the default JSON rule applies.

    Routes opt out of the default ``application/json``-only rule by declaring
    ``accepted_content_types: set[str]`` on their MethodView subclass. The middleware then
    enforces that allowlist instead of the JSON check.
    """
    view = current_app.view_functions.get(request.endpoint or "")
    view_class = getattr(view, "view_class", None)
    accepted = getattr(view_class, "accepted_content_types", None)
    return cast("set[str]", accepted) if isinstance(accepted, (set, frozenset)) else None


def _is_public_endpoint() -> bool:
    """Return True when the current route opts into unauthenticated public access.

    A route declares ``public_access: bool = True`` on its MethodView subclass to be reached
    without a bearer token (e.g. a capability-URL feed). Read by introspection, the same way as
    ``accepted_content_types`` — this keeps the auth middleware free of per-route knowledge.
    """
    view = current_app.view_functions.get(request.endpoint or "")
    view_class = getattr(view, "view_class", None)
    return getattr(view_class, "public_access", False) is True


def register_before_request(base_blueprint: Blueprint, kind: str, sogo_state: int) -> None:  # pylint: disable=too-many-statements
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
    def log_entry() -> ResponseReturnValue | None:  # pylint: disable=too-many-return-statements
        """
        Only used in debug to log request received
        """

        # Log the information
        logger_api.info("Received: \"%s %s %s\"", request.method, request.path, request.environ.get('SERVER_PROTOCOL', 'Unknown'))
        return None
        
    @base_blueprint.before_request
    def check_content_type() -> ResponseReturnValue | None:  # pylint: disable=too-many-return-statements
        """
        Validate the request Content-Type on writes (POST/PATCH/PUT).

        Default rule: only ``application/json`` is accepted, and the body must be syntactically
        valid JSON. A route can opt out by declaring an ``accepted_content_types`` set on its
        view class (e.g. ``{"text/calendar"}`` for the calendar import endpoint). When set,
        the default JSON rule is replaced by a strict mimetype allowlist and the body is left
        untouched — the route is responsible for parsing it.

        :return: An error response when the Content-Type is unsupported or the JSON body is
            malformed, otherwise None.
        :rtype: ResponseReturnValue | None
        """
        if request.method not in {"POST", "PATCH", "PUT"}:
            return None
        content_length = request.content_length
        if content_length is not None and content_length == 0:
            return None
        accepted: set[str] | None = _accepted_content_types()
        if accepted is not None:
            if request.mimetype not in accepted:
                return create_api_base_response(error=err.ERROR_API_CONTENT_TYPE)
            return None
        if not request.is_json:
            return create_api_base_response(error=err.ERROR_API_CONTENT_TYPE)
        data = request.get_data(as_text=True)
        try:
            loads(data)
        except (TypeError, JSONDecodeError):
            return create_api_base_response(error=err.ERROR_API_NOT_JSON)
        return None

    @base_blueprint.before_request
    def get_user() -> ResponseReturnValue | None:
        """
        Add the user/admin instance to Flask g, even if there is no user/admin
        """

        auth_header = request.authorization
        user: User | Admin = UserAnonymous()
        admin: Admin = AdminAnonymous()

        if auth_header:
            if auth_header.type == 'bearer':
                if kind == cs.API_BASIC:
                    user = VoucherUserService(process_config).generate_user_from_voucher(auth_header.token)
                elif kind == cs.API_ADMIN:
                    admin = VoucherAdminService(process_config).generate_admin_from_voucher(auth_header.token)
            elif auth_header.type == 'basic' and current_app.config[cs.ALLOW_AUTH_BASIC]:
                pass
            else:
                return create_api_base_response(error=err.ERROR_WRONG_AUTHORIZATION_TYPE)

        if kind == cs.API_BASIC:
            g.user = user
        elif kind == cs.API_ADMIN:
            g.admin = admin
        return None

    if kind == cs.API_BASIC:
        @base_blueprint.before_request
        def check_non_anonymous_endpoint() -> ResponseReturnValue | None:
            """
            Add the user instance, even if there is no user
            """
            # Skip authentication check for OPTIONS (CORS preflight)
            if request.method == "OPTIONS":
                print("Skipping authentication check for OPTIONS request")
                return None
            anon_endpoints = {
                "user#Auth.v1_Auth.Auth.ApiAuthUserMode", 
                "user#Auth.v1_Auth.Auth.ApiAuthUserLogin",
                "user#Auth.v1_Auth.Auth.ApiAuthUserCallback",
                "user#System.v1_System.System.ApiSystem",
            }
            if (isinstance(g.user, UserAnonymous)
                    and request.endpoint not in anon_endpoints
                    and not _is_public_endpoint()):
                return create_api_base_response(error=err.ERROR_AUTHENTICATED_ROUTE)
            return None

    if kind == cs.API_ADMIN:
        @base_blueprint.before_request
        def check_admin_authenticated() -> ResponseReturnValue | None:
            """
            Check that admin is authenticated for protected endpoints
            """
            # Skip authentication check for OPTIONS (CORS preflight)
            if request.method == "OPTIONS":
                return None

            # Endpoints that don't require admin authentication
            anon_admin_endpoints = {
                "admin#AdminAuth.v1_AdminAuth.AdminAuth.ApiAdminAuthLogin",
            }

            if (isinstance(g.admin, AdminAnonymous)
                    and request.endpoint not in anon_admin_endpoints
                    and not _is_public_endpoint()):
                return create_api_base_response(error=err.ERROR_AUTHENTICATED_ROUTE)
            return None

    if sogo_state == cs.SOGO_NOT_INIT:
        if kind == cs.API_BASIC:
            @base_blueprint.before_request
            def block_sogo() -> ResponseReturnValue:
                """
                Reject requests for basic api id sogo is not init
                """
                return create_api_base_response(error=err.ERROR_SOGO_INIT)
        elif kind == cs.API_ADMIN:
            @base_blueprint.before_request
            def add_process() -> None:
                """
                _Add the process settings in g
                """
                if 'process_settings' not in g:
                    g.process_settings = process_config

    elif sogo_state == cs.SOGO_OK:
        @base_blueprint.before_request
        def get_config_and_user() -> ResponseReturnValue | None:
            """
            Get and set the config in the global flask
            """
            if 'process_settings' not in g:
                g.process_settings = process_config
            system_settings, default_domain_settings = init_get_system_and_default_domain_settings()
            if 'system_settings' not in g:
                g.system_settings = system_settings
            if 'default_domain' not in g:
                g.default_domain_settings = default_domain_settings

            # Handle basic API (user-based)
            if kind == cs.API_BASIC:
                if 'user' in g:
                    user: User = g.user
                    if isinstance(user, UserAnonymous):
                        g.user_domain_settings = default_domain_settings
                    else:
                        g.user_domain_settings = init_get_user_domain_settings(user)
                        inter = InterfaceAuthUser(process_config, system_settings, g.user_domain_settings)
                        creds_ok, new_user = inter.check_user_and_fill_info(user)
                        if not creds_ok:
                            return create_api_base_response(error=err.ERROR_USER_CREDS_NOT_VALID)
                        else:
                            g.user = new_user
                else:
                    logger.error("No user in Flask g")
                    raise AggravatedException("No user in Flask g")
            # Handle admin API (admin-based)
            elif kind == cs.API_ADMIN:
                if 'admin' not in g:
                    logger.error("No admin in Flask g")
                    raise AggravatedException("No admin in Flask g")
            else:
                logger.error("No user in Flask g")
                raise AggravatedException("No user in Flask g")
            return None


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
