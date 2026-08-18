from __future__ import annotations
from typing import TYPE_CHECKING

from app.module.user.ModuleUserShare import ModuleUserShare
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User


class InterfaceUserShare:
    """
    Interface for user shares (folders containing calendars and addressbooks)
    """

    def __init__(self, process_settings: ProcessSetting, user_domain: dict, user: User):
        self.process_settings = process_settings
        self.user = user
        self.user_domain = user_domain
        self.module_user_share = ModuleUserShare(process_settings, user_domain)

    def get_user_share(self) -> tuple[dict, int]:
        """
        Get the user's folders (calendars and addressbooks)

        :return: Tuple containing response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            folders = self.module_user_share.get_user_folders(self.user.uid)
        except RequestException as ex:
            return create_api_base_response(None, ex.error)

        return create_api_base_response(folders)
