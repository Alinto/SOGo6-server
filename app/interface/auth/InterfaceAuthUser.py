from __future__ import annotations
from typing import TYPE_CHECKING, Any

from marshmallow.exceptions import ValidationError

from app.config.db import tables as tbl
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.db.Condition import Order, order_str_to_order_enum
from app.utils.exceptions import RequestException, BugException
from app.utils import errors as err

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.config.settings.SystemSettings import SystemSettingsObj

class InterfaceAuthUser:
    """
    Interface for user authentication
    """

    def __init__(self, process: ProcessSetting, system: SystemSettingsObj, default_domain: dict):

        self.domainless: bool = system.SOGO_S_DOMAINLESS_LOGIN



