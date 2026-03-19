from __future__ import annotations
from typing import TYPE_CHECKING

from app.service import sogo_cache
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger

if TYPE_CHECKING:
    pass


class ModuleAdminUser:
    """
    Module to handle admin operations on users.
    """

    def get_active_users(
        self,
        first: int = 0,
        last: int = 0,
        sort_by: str | None = None,
        sort_order: str = "desc",
        include_fields: str | None = None,
    ) -> tuple[int, list[dict]]:
        """
        Return the list of currently active users by querying the
        ``user_sessions:activity`` sorted set in Redis.

        When *sort_by* is ``None`` the sorted set score (last activity
        timestamp) is used and pagination is performed server-side.
        When *sort_by* is an arbitrary hash field, all hashes are
        fetched, sorted in memory and paginated in memory.

        :param first: 0-based index of the first item to return (pagination)
        :type first: int
        :param last: 0-based index of the last item to return (pagination, exclusive)
        :type last: int
        :param sort_by: field name to sort on (``None`` = last activity / sorted-set score)
        :type sort_by: str | None
        :param sort_order: ``"asc"`` or ``"desc"`` (default ``"desc"`` = most recent first)
        :type sort_order: str
        :param include_fields: comma-separated list of fields to keep
        :type include_fields: str | None
        :return: Tuple of (total_count, list of active user dicts)
        :rtype: tuple[int, list[dict]]
        :raises RequestException: If the cache query fails
        """
        cache = sogo_cache()

        try:
            total_count, active_users = cache.zset_paginate_hashes(
                #zset_key=cs.ZSET_USER_SESSIONS_ACTIVITY,
                first=first,
                last=last,
                sort_by=sort_by,
                sort_order=sort_order,
                include_fields=include_fields,
            )
        except Exception as e:
            raise RequestException(str(e), error=err.ERROR_CACHE_SCAN_FAILED) from e

        logger.debug("%d active user session(s) (total: %d)", len(active_users), total_count)
        return total_count, active_users

    def revoke_users(self, uids: list[str]) -> int:
        """
        Revoke all cache sessions for the given UIDs.

        :param uids: list of user UIDs to revoke
        :type uids: list[str]
        :return: number of sessions revoked
        :rtype: int
        :raises RequestException: If the cache operation fails
        """
        cache = sogo_cache()

        try:
            revoked_count = cache.revoke_user_sessions(uids)
        except Exception as e:
            raise RequestException(str(e), error=err.ERROR_CACHE_REVOKE_FAILED) from e

        logger.debug("Revoked %d session(s) for uid(s): %s", revoked_count, uids)
        return revoked_count
