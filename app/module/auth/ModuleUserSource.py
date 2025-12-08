from __future__ import annotations
from typing import TYPE_CHECKING, Any, Type, Callable

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj

class ModuleUserSource:
    """
    Module to handle authentication. Thos module oly take one user source.
    """
    def __init__(self, user_source: UserSourceSettingsObj):
        """
        """
        self.us_type  = user_source.US_KIND

    def check_login(self, uid:str, password:str) -> bool:
        """
        Check the login in the user source

        :param uid: username/mail/uid of the suer
        :type uid: str
        :param password: password
        :type password: str
        :return: True if the user is correctly authenticated
        :rtype: bool
        """
        ret = uid in ("sogo-tests1@example.org", "sogo-tests2@example.org", "sogo-tests3@example.org")
        ret = ret and password == "sogo"
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

        
