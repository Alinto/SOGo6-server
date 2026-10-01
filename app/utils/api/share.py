from flask import g

from app.config.settings.DomainSettings import UserModuleSettings
from app.utils import constants as cs


def is_share_any_auth_forbidden(module: str, share_data: list[dict]) -> bool:
    """
    Check if a share payload grants rights to "anyone" while the domain forbids it.

    :param module: module name as listed in SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH ('mail', 'calendar', 'contact')
    :type module: str
    :param share_data: share entries from the request body
    :type share_data: list[dict]
    :return: True if one entry targets "anyone" and SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH contains the module
    :rtype: bool
    """
    user_module_settings: dict = g.user_domain_settings.get(UserModuleSettings.subparent, {})
    if module not in user_module_settings.get("SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH", []):
        return False
    return any(entry.get("user_class") == cs.USER_CLASS_ANY for entry in share_data)
