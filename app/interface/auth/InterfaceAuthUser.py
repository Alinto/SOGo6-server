from __future__ import annotations
from typing import TYPE_CHECKING, Any

from marshmallow.exceptions import ValidationError

from app.auth.User import User
from app.config.db import tables as tbl
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.db.Condition import Order, order_str_to_order_enum
from app.utils.exceptions import RequestException, BugException
from app.utils import errors as err
from app.utils.strings import get_domain_from_mail

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.config.settings.SystemSettings import SystemSettingsObj

class InterfaceAuthUser:
    """
    Interface for user authentication
    """

    def __init__(self, process: ProcessSetting, system: SystemSettingsObj, default_domain: dict):

        self.domainless = system.SOGO_S_DOMAINLESS_LOGIN
        self.reject_unknown_domain = system.SOGO_S_REJECT_UNKNOWN_DOMAIN
        self.known_domains = system.SOGO_S_KNOWN_DOMAIN

    def get_login_mech(self, user_uid:str, redirect:str) -> tuple[dict, int]:
        """
        Get the login mech from a uid

        :param user_uid: _description_
        :type user_uid: str
        :return: _description_
        :rtype: tuple[dict, int]
        """
        if not self.domainless:
            domain = get_domain_from_mail(user_uid)
            if not domain:
                return create_api_base_response({}, err.ERROR_LOGIN_NO_DOMAIN), 400
            if self.reject_unknown_domain:
                pass

        ret = {
            "kind": "plain",
            "location": ""
        }
        return create_api_base_response(ret), 200
    
    def plain_login(self, data:dict) -> dict:
        """
        Check a plain login uid/password

        :param data: _description_
        :type data: dict
        """
        uid = data["uid"]
        password = data["password"]
        if self.domainless:
            user = User(uid, password, is_domainless=True)
        else:
            domain = get_domain_from_mail(uid)
            user = User(uid, password, domain=domain)
        
        ret = user.check_login()

        return {}



