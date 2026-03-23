from __future__ import annotations
from typing import TYPE_CHECKING, Tuple, Dict, Any

from app.module.admin.ModuleAdminUser import ModuleAdminUser
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceApiAdminUser:
    """
    Interface for the admin user API (ApiAdminUser).
    """

    def __init__(self, process_setting: ProcessSetting) -> None:
        """
        :param process_setting: the process settings
        :type process_setting: ProcessSetting
        """
        self.module = ModuleAdminUser()

    def get_active_users(
        self,
        first: int = 0,
        last: int = 0,
        sort_by: str | None = None,
        sort_order: str = "desc",
        include_fields: str | None = None,
    ) -> Tuple[int, Dict[str, Any], int]:
        """
        Return the list of currently active users.

        When *sort_by* is None the sorted-set score (last activity)
        is used and pagination is server-side.  Any other value triggers
        an in-memory sort over all sessions.

        :param first: 0-based index of the first item (pagination)
        :type first: int
        :param last: 0-based index of the last item (pagination, exclusive)
        :type last: int
        :param sort_by: field name to sort on (None = last activity)
        :type sort_by: str | None
        :param sort_order: "asc" or "desc" (default "desc" = most recent first)
        :type sort_order: str
        :param include_fields: comma-separated list of fields to keep
        :type include_fields: str | None
        :return: Tuple of (item_count, API response dict, HTTP status code)
        :rtype: Tuple[int, Dict[str, Any], int]
        """
        try:
            total_count, active_users = self.module.get_active_users(
                first=first,
                last=last,
                sort_by=sort_by,
                sort_order=sort_order,
                include_fields=include_fields,
            )
        except RequestException as ex:
            logger_api.error("Request exception in get_active_users: %s", str(ex))
            return 0, *create_api_base_response(None, ex.error)
        return total_count, *create_api_base_response(active_users)

    def revoke_users(self, uids: list[str] | None = None, redis_keys: list[str] | None = None) -> Tuple[Dict[str, Any], int]:
        """
        Revoke cache sessions either by UID or by direct Redis key.

        Exactly one of *uids* or *redis_keys* must be provided.

        :param uids: list of user UIDs to revoke (mutually exclusive with *redis_keys*)
        :type uids: list[str] | None
        :param redis_keys: list of Redis hash keys to revoke (mutually exclusive with *uids*)
        :type redis_keys: list[str] | None
        :return: Tuple of (API response dict, HTTP status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            revoked_count = self.module.revoke_users(uids=uids, redis_keys=redis_keys)
        except RequestException as ex:
            logger_api.error("Request exception in revoke_users: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response({"revoked": revoked_count})
