"""
Admin authentication API endpoints
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, request, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.admin.InterfaceApiAdminAuth import InterfaceAdminAuth
from app.utils.logger.logger import logger_api

from .schema import adminAuth as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


blp = Blueprint("AdminAuth", __name__, url_prefix="/auth")


@blp.before_request
def init_admin_auth_interface() -> None:
    """
    Initialize the admin auth interface for this request
    """
    logger_api.debug("Calling before_request for AdminAuth")
    process: ProcessSetting = g.process_settings
    interface_api = InterfaceAdminAuth(process)
    g.inter = interface_api


@blp.route("/login")
class ApiAdminAuthLogin(MethodView):
    """
    Admin login endpoint
    """

    @blp.arguments(sch.AdminAuthBasicPostSchema, example=sch.AdminAuthBasicPostSchema.example(), error_status_code=400)
    @blp.response(200)
    def post(self, new_data: dict) -> ResponseReturnValue:
        """
        Authenticate admin with username and password.
        Returns a JWT token for subsequent requests.
        """
        username = new_data["username"]
        password = new_data["password"]
        interface_api: InterfaceAdminAuth = g.inter
        return interface_api.admin_login(username, password)


@blp.route("/logout")
class ApiAdminAuthLogout(MethodView):
    """
    Admin logout endpoint
    """

    @blp.response(200)
    def post(self) -> ResponseReturnValue:
        """
        Logout the authenticated admin by revoking the session associated
        with the JWT token present in the Authorization header.
        """
        auth_header = request.authorization
        voucher_data: str = auth_header.token if auth_header else ""
        interface_api: InterfaceAdminAuth = g.inter
        return interface_api.admin_logout(voucher_data)
