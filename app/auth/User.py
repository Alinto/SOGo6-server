from __future__ import annotations
from typing import TypeVar
from abc import ABCMeta, abstractmethod

from app.utils.strings import get_domain_from_mail
from app.utils import constants as cs

class User:
    """
    Reprensation of a User, can be anonymous
    """

    @staticmethod
    def init_from_user_session(user_session:dict, is_domainless:bool = False) -> User:
        """
        Create a User instance from a payload

        :param payload: _description_
        :type payload: dict
        :param is_domainless: _description_, defaults to False
        :type is_domainless: bool, optional
        :return: _description_
        :rtype: User
        """
        uid = user_session[cs.USER_UID]
        password = user_session[cs.USER_PWD]
        domain = user_session[cs.USER_DOMAIN]
        user = User(uid, password, domain=domain, is_domainless=is_domainless)
        user.mail = user_session[cs.USER_EMAIL]
        return user

    def __init__(self, uid:str, password:str, cn:str= "", domain:str= "", is_domainless:bool = False):
        """
        _summary_

        :param uid: Unique identifier of the user in the user source, often be the mail but could be anything
        :type uid: str
        :param password: password of the user, used to login (mail password can be different)
        :type password: str
        :param cn: Common name of the user "John Doe", defaults to ""
        :type cn: str, optional
        :param domain: domain of the user, defaults to ""
        :type domain: str, optional
        :param is_domainless: True if sogo use domainless login, defaults to False
        :type is_domainless: bool, optional
        """
        self.uid = uid
        self.cn = cn
        self.password = password
        self.is_domainless = is_domainless
        self.authenticated = False

        uid_domain = get_domain_from_mail(uid)


        self.domain: str = domain

        if not domain and uid_domain:
            self.domain = uid_domain

        #Those will be set after the login is checked
        self.mail: str = ""  #Don't assume that mail = uid or mail = uid + domain. Uid can be anything.
        self.source_id: str = "" #Set to avoid checking several user sources in the future for this user.


    def check_login(self) -> bool:
        """
        Check the credetnials of the user

        :return: _description_
        :rtype: bool
        """
        ret = self.uid in ("sogo-tests1@example.org", "sogo-tests2@example.org", "sogo-tests3@example.org")
        ret = ret and self.password == "sogo"
        self.authenticated = ret
        
        return ret


    def get_user_session(self) -> dict:
        """
        The user session is stored by the server ans is used to 
        instantiate the user after a aunthenticated request.

        :return: _description_
        :rtype: dict
        """
        ret = {
            cs.USER_UID:    self.uid,
            cs.USER_PWD:    self.password,
            cs.USER_DOMAIN: self.domain,
            cs.USER_EMAIL:  self.mail
        }

        return ret

    def get_voucher_payload(self) -> dict:
        """
        The voucher is send to the API client.


        :return: _description_
        :rtype: dict
        """
        ret = {
            cs.USER_UID: self.uid,
            cs.USER_CN: self.cn,
            cs.USER_EMAIL: self.mail
        }

        return ret
