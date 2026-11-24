from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis


@dataclass(frozen=True)
class DavContext:
    """Configuration, user and cache client of one DAV request, built by the authentication of the handler.

    The DAV counterpart of what the REST API keeps in Flask ``g``. ``user`` is authenticated, filled
    with its directory info and profile, and keeps the password in memory for the mail servers. ``cache``
    is not closed: its connection is closed when it is freed with the request. ``account_alias`` is the part
    after "!" of a login "<login>!<alias>", None without "!": it ends the account in the paths (see DavPath).
    """

    process_settings: ProcessSetting
    system_settings: dict
    user_domain_settings: dict
    user: User
    cache: ClientRedis
    account_alias: str | None
