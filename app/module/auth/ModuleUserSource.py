from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj
    from app.auth.User import User

class ModuleUserSource:
    """
    Module to handle UserSources. Plural because they may be several users sources.
    There are rules between the differents users sources about visibility.

    """
    def __init__(self, list_user_source: dict[str, UserSourceSettingsObj]):
        """
        list_user_source is a dict where the keys are the soruce uid
        """
        self.list_user_source = list_user_source


    def check_login(self, user:User) -> bool:
        """
        Check the login in the user source

        :param uid: username/mail/uid of the suer
        :type uid: str
        :param password: password
        :type password: str
        :return: True if the user is correctly authenticated
        :rtype: bool
        """
        if user.source_id and user.source_id in self.list_user_source:
            source_settings = self.list_user_source[user.source_id]
        else:
            #No source id yet or source_id is not relevant anymore
            for source_uid, source_settings in self.list_user_source.items():
                if source_settings.US_CAN_AUTH:
                    us_type = source_settings.US_TYPE
                    #TODO Dynamically import the relevant manager according to the us_type

        ret = user.uid in ("sogo-tests1@example.org", "sogo-tests2@example.org", "sogo-tests3@example.org")
        ret = ret and user.password == "sogo"
        contact_info = self.get_contact_info(user.uid)
        user.cn = contact_info["cn"]
        user.mail = contact_info["email"]
        user.source_id = "ldap.ex"
        user.authenticated = True
        return ret

    def get_contact_info(self, uid:str) -> dict:
        """
        Return the contact info of the user

        :param uid: _description_
        :type uid: str
        """
        ret = {
            "sogo-tests1@example.org": {
                "uid": "sogo-tests1@example.org",
                "cn": "John Paul",
                "email": "sogo-tests1@example.org"
            },
            "sogo-tests2@example.org": {
                "uid": "sogo-tests2@example.org",
                "cn": "John Paul",
                "email": "sogo-tests2@example.org"
            },
            "sogo-tests3@example.org": {
                "uid": "sogo-tests3@example.org",
                "cn": "John Paul",
                "email": "sogo-tests3@example.org"
            }
        }
        return ret[uid]

