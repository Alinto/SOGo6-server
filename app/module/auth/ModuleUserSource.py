from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.settings.DomainSettings import UserSourceSettingsObj, UserSourceSettings
from app.utils import exceptions as exc
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.user_source.ClientUserSource import ClientUserSource

MAP_KEY_CLASS = {
    "ldap": "ClientLdap",
    "mysql": "ClientMySQL",
    "postgresql": "ClientPostgreSQL"
}

MAP_KEY_PATH = {
    "ldap": "app.manager.ldap",
    "mysql": "app.manager.db",
    "postgresql": "app.manager.db"
}

class ModuleUserSource:
    """
    Module to handle UserSources. Plural because they may be several users sources.
    There are rules between the differents users sources about visibility.

    """

    @staticmethod
    def init_from_domain_settings(domain_settings:dict) -> ModuleUserSource:
        """
        Init the Module User Source from the domain settings

        :param domain_settings: Domain settings
        :type domain_settings: dict
        :return: self
        :rtype: ModuleUserSource
        """
        all_user_sources: dict = {}
        domain_user_sources: dict = domain_settings[UserSourceSettings.subparent]
        for user_source_id, user_source in domain_user_sources.items():
            all_user_sources[user_source_id] = UserSourceSettingsObj(user_source)
        return ModuleUserSource(all_user_sources)

    def __init__(self, all_user_sources: dict[str, UserSourceSettingsObj]):
        """
        list_user_source is a dict where the keys are the soruce uid
        """
        self.all_user_sources = all_user_sources

    def _make_us_check_login(self, source_settings: UserSourceSettingsObj, user: User) -> tuple[bool, dict, dict[str, list[str]]]:
        """
        _summary_

        :param source_settings: _description_
        :type source_settings: UserSourceSettingsObj
        :param user: _description_
        :type user: User
        :return: _description_
        :rtype: tuple[bool, dict, dict]
        """
        us_config = source_settings.get_user_source_settings(source_settings.US_TYPE)
        client_us: ClientUserSource = import_and_instantiate_manager(
            module_path=MAP_KEY_PATH[source_settings.US_TYPE],
            module_and_class_name=MAP_KEY_CLASS[source_settings.US_TYPE],
            module_args=us_config,
        )
        client_us.connect()
        return client_us.check_login(user.uid, user.password, user.domain)

    def check_login(self, user:User) -> bool:
        """
        Check the login in the user source

        :param user: User object containing authentication information
        :type user: User
        :return: True if the user is correctly authenticated
        :rtype: bool
        """
        auth = False
        raw_policy: dict = {}
        raw_content: dict[str, list[str]] = {}
        if user.source_id and user.source_id in self.all_user_sources:
            source_settings = self.all_user_sources[user.source_id]
            if source_settings.US_CAN_AUTH:
                logger.warning("Registered user source %s for user %s forbid authentication." \
                "Might happend if the user source US_CAN_AUTH has changed", user.source_id, user.uid)
            else:
                auth, raw_policy, raw_contact = self._make_us_check_login(source_settings, user)
                if not auth:
                    return False
                user.authenticated = True

        for source_uid, source_settings in self.all_user_sources.items():
            if source_settings.US_CAN_AUTH:
                auth, raw_policy, raw_contact = self._make_us_check_login(source_settings, user)
                if not auth:
                    #User not found in this user source, check the next one
                    continue
                user.source_id = source_uid
                user.authenticated = True
                break

        if not user.authenticated:
            # Creds false or user missing from user source
            return False

        #Get user info
        self.fill_user_with_contact_info(user, raw_contact)
        self.fill_user_with_source_info(user, raw_contact)
        return auth


    def fill_user_with_contact_info(self, user:User, user_info:dict) -> None:
        """
        Fill user with the contact info

        :param uid: The user unique ID
        :type uid: str
        :return: Dictionary containing user contact information (uid, cn, email)
        :rtype: dict
        """
        user.cn =   user_info["cn"][0]
        user.mail = user_info["mail"][0]

        #At this stage, the user must have a source_id as it already has been logged in.
        if not user.source_id or user.source_id not in self.all_user_sources:
            raise exc.AggravatedException("User with no source_id")

        user_source_settings = self.all_user_sources[user.source_id]

        #Check for others mails address
        for key_mail in user_source_settings.US_MAIL:
            for new_mail in user_info.get(key_mail, []):
                if new_mail != user.mail:
                    user.extra_mail.append(new_mail)

        #Check if we have extra info in the user_info
        if user_source_settings.US_MAPPING:
            for key_sogo, key_user_source in user_source_settings.US_MAPPING.items():
                if info := user_info.get(key_user_source):
                    #TODO parse into contactCard, beware that each user_info is a list and my need to be a signle value
                    user.extra_info[key_sogo] = info


    def fill_user_with_source_info(self, user:User, user_info:dict) -> None:
        """
        WIll fecth the user source for extra info required by user source config.
        Mainly there is the US_MAPPING wich are contact info.
        Secondly there is some mails parameters, and module access.

        :param user: _description_
        :type user: User
        """
        #At this stage, the user mus have a source_id as it already has been logged in.
        if not user.source_id or user.source_id not in self.all_user_sources:
            raise exc.AggravatedException("User with no source_id")

        user_source_settings = self.all_user_sources[user.source_id]

        # Get, if needed, the proper login for mail
        user.login_mail_server = user.mail
        user.login_mail_outgoing = user.mail
        user.login_mail_filtering = user.mail
        if user_source_settings.US_MAIL_SERVER_LOGIN:
            user.login_mail_server = user_info.get(user_source_settings.US_MAIL_SERVER_LOGIN, user.mail)
        if user_source_settings.US_MAIL_OUTGOING_LOGIN:
            user.login_mail_outgoing = user_info.get(user_source_settings.US_MAIL_OUTGOING_LOGIN, user.mail)
        if user_source_settings.US_MAIL_FILTERING_LOGIN:
            user.login_mail_filtering = user_info.get(user_source_settings.US_MAIL_FILTERING_LOGIN, user.mail)

        # Get, if needed, the proper imap DEPERACTED
        if user_source_settings.US_IMAP_HOST_FIELDNAME:
            user.imap_host = user_info.get(user_source_settings.US_IMAP_HOST_FIELDNAME, "")

        if user_source_settings.US_MODULE_ACCESS:
            for module_name, conditions in user_source_settings.US_MODULE_ACCESS.items():
                for cond_name, cond_value in conditions.items():
                    if user_info.get(cond_name, None) == cond_value:
                        setattr(user.access, module_name.lower(), False)


    def _get_contact_info_for_user_from_user_source(self, user:User) -> dict:
        """
        _summary_

        :param user: _description_
        :type user: _type_
        :return: _description_
        :rtype: dict
        """
        #TODO fetch the user source
        return {}

    def get_contact_info_for_user(self, user:User) -> None:
        """
        Get a user and fill it with infos from user source

        :param user: user to fill
        :type user: User
        """
        infos = self._get_contact_info_for_user_from_user_source(user)
        if not infos:
            user.anonymous = True
        else:
            self.fill_user_with_contact_info(user, infos)
            self.fill_user_with_source_info(user, infos)
