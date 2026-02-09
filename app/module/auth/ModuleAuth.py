from __future__ import annotations
from typing import TYPE_CHECKING


from app.auth.User import User
from app.auth.service.VoucherUserService import VoucherUserService
from app.config.db import tables as tbl
from app.config.settings.DomainSettings import AuthSettings, UserSourceSettings
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import RequestException
from app.utils.strings import get_domain_from_mail
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import AuthSettingsObj, UserSourceSettingsObj
    from app.config.settings.SystemSettings import SystemSettingsObj
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL

class ModuleAuth:
    """
    Module to handle authentication. Thos module only take one user source.
    """
    def __init__(self, process: ProcessSetting,
                 system: SystemSettingsObj,
                 default_auth_settings: AuthSettingsObj,
                 default_us_source: dict[str, UserSourceSettingsObj]):
        """
        Initialize the authentication module

        :param process: Process settings
        :type process: ProcessSetting
        :param system: System settings object
        :type system: SystemSettingsObj
        :param default_auth_settings: Default authentication settings
        :type default_auth_settings: AuthSettingsObj
        :param default_us_source: Default user source settings mapped by source UID
        :type default_us_source: dict[str, UserSourceSettingsObj]
        """
        self.process_settings = process

        self.do_domains     = system.SOGO_S_DO_DOMAIN
        self.domainless     = system.SOGO_S_DOMAINLESS_LOGIN
        self.known_domains  = system.SOGO_S_KNOWN_DOMAIN
        self.reject_unknown = system.SOGO_S_REJECT_UNKNOWN_DOMAIN

        self.default_auth = default_auth_settings
        self.default_us = default_us_source

    def _check_domain(self, uid:str) -> str:
        """
        Check if a domain is found and if it matches system settings rules

        :param uid: The user unique ID
        :type uid: str
        :raises RequestException: When no domain is given but domainless login is disabled
        :raises RequestException: When domain is not in known domains and unknown domains are rejected
        :return: empty string or the domain
        :rtype: str
        """
        domain = ""
        if not self.domainless:
            tmp_domain = get_domain_from_mail(uid)
            if not tmp_domain:
                raise RequestException("No domain given for auth when this is required")
            if self.reject_unknown and tmp_domain not in self.known_domains:
                raise RequestException("Domain given for auth is not registered in SOGO_S_REJECT_UNKNOWN_DOMAIN")
            domain = tmp_domain
        return domain

    def _get_domain_auth_and_user_source_settings(self, domain:str) -> tuple[AuthSettingsObj, dict[str, UserSourceSettingsObj]]:
        """
        Return the authentication and user source settings for this domain, or the default ones

        :param domain: The domain name
        :type domain: str
        :return: Tuple containing auth settings and user source settings mapped by source UID
        :rtype: tuple[AuthSettingsObj, dict[str, UserSourceSettingsObj]]
        """
        domain_auth_settings = self.default_auth
        domain_user_source = self.default_us
        if domain and self.do_domains:
            fake_process_settings_db = self.process_settings.SOGO_P_DB_TYPE
            sogo_db_type = f"Client{fake_process_settings_db}"

            sogo_db_manager: ClientSQL = import_and_instantiate_manager(module_path="app.manager.db",
                                                            module_and_class_name=sogo_db_type,
                                                            module_args=self.process_settings.get_db_settings())
            condition = EqualCondition(tbl.COL_DOMAIN_NAME.name, domain)
            sogo_db_manager.connect()
            result = list(sogo_db_manager.select_from_table(tbl.TABLE_DOMAIN.name,
                                                (tbl.COL_DOMAIN_SETTINGS.name,),
                                                condition=condition))

            if len(result) == 1:
                domain_auth_settings = AuthSettingsObj(result[0][0]["AUTH_SETTINGS"])
                domain_user_source_raw = result[0][0]["USER_SOURCE"]
                domain_user_source = {}
                for source_uid, source_settings in domain_user_source_raw.items():
                    domain_user_source[source_uid] = UserSourceSettingsObj(source_settings)

        return domain_auth_settings, domain_user_source

    def get_login_mech(self, uid:str) -> dict:
        """
        Get the login mechanism for this uid

        :param uid: username/mail/uid of the user
        :type uid: str
        :return: Dictionary containing the authentication kind and location
        :rtype: dict
        """

        domain = self._check_domain(uid)
        domain_auth_settings, _ = self._get_domain_auth_and_user_source_settings(domain)

        kind = domain_auth_settings.SOGO_D_AUTH_TYPE


        #TODO Only work for plain login, do it properly for openid,cas...
        ret = {
            "kind": kind,
            "location": ""
        }
        return ret

    def get_user_and_domain_user_sources(self, username:str, password:str) -> tuple[User, dict[str, UserSourceSettingsObj]]:
        """
        Prepare a User object for plain login authentication and get the domain user sources

        :param username: username/mail/uid of the user
        :type username: str
        :param password: password
        :type password: str
        :return: Tuple of (User object ready for authentication, domain user sources settings)
        :rtype: tuple[User, dict[str, UserSourceSettingsObj]]
        """

        domain = self._check_domain(username)
        _, domain_user_sources = self._get_domain_auth_and_user_source_settings(domain)

        if self.domainless:
            user = User(username, password, is_domainless=True)
        else:
            user = User(username, password, domain=domain)

        return user, domain_user_sources

    def generate_voucher_from_user(self, user: User) -> dict:
        """
        Generate a voucher from an authenticated user

        :param user: Authenticated user object
        :type user: User
        :return: Dictionary containing the jwt_token
        :rtype: dict
        """
        voucher_user_service = VoucherUserService(self.process_settings)
        voucher_data = voucher_user_service.generate_voucher_from_user(user)
        return {"jwt_token": voucher_data}
