from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.admin.InterfaceApiAdminUser import InterfaceApiAdminUser
from app.utils.logger.logger import logger_api
from app.utils.api.paginate_sort_filter import collection_paginate, CustomPaginateResponse

from .schema import adminUser as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


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
    @collection_paginate(blp, sort_value_set=sch.AdminUserActiveSchema.sort_by_values(), can_filter=False)
    def get(self, collection_param: CollectionPaginateArgs) -> CustomPaginateResponse:
        """
        Get the list of currently active users.

        Returns all users that have a live session in the cache, together
        with their last activity timestamp.

        :param collection_param: The object for pagination, sorting anf filtering
        :type collection_param: CollectionPaginateArgs
        :return: A tuple of (item count, API response dict, status code)
        :rtype: Tuple[int, dict, int]
        """
        logger_api.debug("Calling ApiAdminUserActive: Fetching active users: %s", collection_param)
        interface: InterfaceApiAdminUser = g.inter

        item_count, response, status_code = interface.get_active_users(collection_param)

        #return response, status_code
        return item_count, response, status_code


@blp.route("/revoke")
class ApiAdminUserRevoke(MethodView):
    """
    Revoke one or several user sessions from the cache.

    Sending a list of UIDs will immediately invalidate all active sessions
    belonging to those users.
    """

    @blp.arguments(sch.AdminUserRevokeBodySchema, example=sch.AdminUserRevokeBodySchema.example(), error_status_code=400)
    @blp.response(200, sch.AdminUserRevokeSchema, example=sch.AdminUserRevokeSchema.example())
    def post(self, body: dict) -> ResponseReturnValue:
        """
        Revoke all active sessions for the given UIDs.

        Accepts a list of UIDs and removes every matching session hash from the
        cache as well as all sorted-set indexes.  Returns the total number of
        sessions that were deleted.

        :param body: Request body containing the list of UIDs to revoke
        :type body: dict
        :return: API response dict with the revoke count
        :rtype: ResponseReturnValue
        """
        uids: list[str] | None = body.get("uid")
        redis_keys: list[str] | None = body.get("redis_key")
        logger_api.debug("Calling ApiAdminUserRevoke: revoking sessions for uids: %s, redis_keys: %s", uids, redis_keys)

        interface: InterfaceApiAdminUser = g.inter
        response, status_code = interface.revoke_users(uids=uids, redis_keys=redis_keys)

        return response, status_code


@blp.route("/inactive")
class ApiAdminUserInactive(MethodView):
    """
    Revoke inactive user sessions from the cache.

    Sending a Unix timestamp will remove all sessions whose last activity
    is older than (≤) that timestamp.
    """

    @blp.arguments(sch.AdminUserInactiveBodySchema, example=sch.AdminUserInactiveBodySchema.example(), error_status_code=400)
    @blp.response(200, sch.AdminUserInactiveSchema, example=sch.AdminUserInactiveSchema.example())
    def post(self, body: dict) -> ResponseReturnValue:
        """
        Revoke all sessions whose last activity is older than the given timestamp.

        Accepts a Unix timestamp and removes every session hash from the
        cache whose last-activity score is ≤ that value, along with all
        sorted-set index entries.  Returns the total number of sessions
        that were deleted.

        :param body: Request body containing the timestamp
        :type body: dict
        :return: API response dict with the revoke count
        :rtype: ResponseReturnValue
        """
        timestamp: int = body["timestamp"]
        logger_api.debug("Calling ApiAdminUserInactive: revoking sessions older than %d", timestamp)

        interface: InterfaceApiAdminUser = g.inter
        response, status_code = interface.revoke_inactive_users(timestamp=timestamp)

        return response, status_code
