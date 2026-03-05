from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.admin.InterfaceApiAdminUser import InterfaceApiAdminUser
from app.utils.logger.logger import logger_api
from app.utils.api.paginate_sort_filter import custom_paginate

from .schema import adminUser as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


blp = Blueprint("Admin Users", __name__, url_prefix="/users")


@blp.before_request
def init_admin_user() -> None:
    """
    Initialize the interface and anything else required for the request.
    """
    logger_api.debug("Calling before_request for ApiAdminUser")
    process: ProcessSetting = g.process_settings
    interface_api = InterfaceApiAdminUser(process_setting=process)
    g.inter = interface_api


@blp.route("/active")
class ApiAdminUserActive(MethodView):
    """
    Collection of currently active users.

    An active user is a user who has a valid session stored in the cache.
    """

    @blp.response(200, sch.AdminUserActiveSchema, example=sch.AdminUserActiveSchema.example())
    @custom_paginate(blp)
    def get(self, first: int, last: int, fields_args: dict, sort_args: dict) -> ResponseReturnValue:
        """
        Get the list of currently active users.

        Returns all users that have a live session in the cache, together
        with their last activity timestamp.

        :param first: The index of the first item to retrieve (for pagination)
        :type first: int
        :param last: The index of the last item to retrieve (for pagination)
        :type last: int
        :param fields_args: The fields to include in the response (for field filtering)
        :type fields_args: dict
        :param sort_args: The sorting parameters (for sorting)
        :type sort_args: dict
        :return: A tuple of (item count, API response dict, status code)
        :rtype: Tuple[int, dict, int]
        """
        logger_api.debug(
            "Calling ApiAdminUserActive: Fetching active users, first: %s, last: %s, sort_by: %s, sort_order: %s, fields: %s",
            first, last,
            sort_args.get("sort_by"), sort_args.get("sort_order"),
            fields_args.get("include_fields"),
        )
        interface: InterfaceApiAdminUser = g.inter

        item_count, response, status_code = interface.get_active_users(
            first=first,
            last=last,
            sort_by=sort_args.get("sort_by"),
            sort_order=sort_args.get("sort_order", "desc"),
            include_fields=fields_args.get("include_fields"),
        )

        return item_count, response, status_code
