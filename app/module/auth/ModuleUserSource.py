from __future__ import annotations
from typing import TYPE_CHECKING

from app.utils import exceptions as exc

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj
    from app.auth.User import User

class ModuleUserSource:
    """
    Module to handle UserSources. Plural because they may be several users sources.
    There are rules between the differents users sources about visibility.

    """
    def __init__(self, all_user_sources: dict[str, UserSourceSettingsObj]):
        """
        list_user_source is a dict where the keys are the soruce uid
        """
        self.all_user_sources = all_user_sources


    def check_login(self, user:User) -> bool:
        """
        Check the login in the user source

        :param user: User object containing authentication information
        :type user: User
        :return: True if the user is correctly authenticated
        :rtype: bool
        """
        if user.source_id and user.source_id in self.all_user_sources:
            source_settings = self.all_user_sources[user.source_id]
        else:
            #No source id yet or source_id is not relevant anymore
            for source_uid, source_settings in self.all_user_sources.items():
                if source_settings.US_CAN_AUTH:
                    us_type = source_settings.US_TYPE
                    #TODO Dynamically import the relevant manager according to the us_type

        ret = user.uid in ("sogo-tests1@example.org", "sogo-tests2@example.org", "sogo-tests3@example.org")
        ret = ret and user.password == "sogo"

        user.source_id = "ldap_ex"
        user.authenticated = True

        #Get user info
        user_info = self.fake_user_source_lookup(user.uid)
        self.fill_user_with_contact_info(user, user_info)
        self.fill_user_with_source_info(user, user_info)
        return ret


    def fake_user_source_lookup(self, uid:str) -> dict:
        """
        Return the infos from the user source for this uid

        :param uid: The user unique ID
        :type uid: str
        :return: Dictionary containing user contact information (uid, cn, email)
        :rtype: dict
        """
        ret : dict[str, dict] = {
            "sogo-tests1@example.org": {
                "uid": "sogo-tests1@example.org",
                "cn": "John Paul",
                "email": "sogo-tests1@example.org",
                "aliases": ["jpaul@example.org", "dpo@example.org"],
                "telephone": "555-3647"
            },
            "sogo-tests2@example.org": {
                "uid": "sogo-tests2@example.org",
                "cn": "John Paul",
                "email": "sogo-tests2@example.org"
            },
            "sogo-tests3@example.org": {
                "uid": "sogo-tests3@example.org",
                "cn": "John Paul",
                "email": "sogo-tests3@example.org",
                "login_imap": "bernard",
                "login_smtp": "bernard",
                "login_sieve": "bernard",
                "imap_host": "127.0.0.1",
                "c_ou": "extern"
            }
        }
        return ret.get(uid, {})

    def fill_user_with_contact_info(self, user:User, user_info:dict) -> None:
        """
        Fill user with the contact info

        :param uid: The user unique ID
        :type uid: str
        :return: Dictionary containing user contact information (uid, cn, email)
        :rtype: dict
        """
        user.cn =   user_info["cn"]
        user.mail = user_info["email"]

        #At this stage, the user mus have a source_id as it already has been logged in.
        if not user.source_id or user.source_id not in self.all_user_sources:
            raise exc.AggravatedException("User with no source_id")

        user_source_settings = self.all_user_sources[user.source_id]

        #Check for others mails address
        for key_mail in user_source_settings.US_MAIL:
            new_mail: str
            if (new_mail := user_info.get(key_mail, None)) and new_mail != user.mail:
                user.extra_mail.append(new_mail)

        #Check if we have extra info in the user_info
        if user_source_settings.US_MAPPING:
            for key_sogo, key_user_source in user_source_settings.US_MAPPING.items():
                if info := user_info.get(key_user_source):
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
    
    def fill_user(self, user:User) -> None:
        """
        Get a user and fill it with infos from user source

        :param user: user to fill
        :type user: User
        """
        infos = self.fake_user_source_lookup(user.uid)
        self.fill_user_with_contact_info(user, infos)
        self.fill_user_with_source_info(user, infos)
