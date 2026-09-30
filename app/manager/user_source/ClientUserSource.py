from abc import ABCMeta, abstractmethod
from typing import Generator

from app.utils.db.Condition import Condition
from app.utils.logger.logger import logger

class ClientUserSource(metaclass=ABCMeta):
    """
    Abstract class for user source.
    All user source clients (ldap, sql, ...) should inherit from this class and implement its methods.
    """
    def __init__(self) -> None:
        """
        Just set a param to tell if the client needs to authenticate or not
        """
        self.connected = False
        self.authenticated = False

    @abstractmethod
    def connect(self) -> None:
        """
        Connect to the user source server.
        """
        logger.error("Method 'connect' of ClientUserSource must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError


    @abstractmethod
    def check_login(self, username: str, password: str, domain:str) -> tuple[bool, dict, dict[str, list[str]]]:
        """
        Check the credentials of a usermary

        Returns a tuple:
        * bool, True if the login has been successful
        * dict, Extra info for the login/passwword policy
        * dict, contact Info

        :param username: username, uid or mail
        :type username: str
        :param password: password, token
        :type password: str
        :param domain: mail's domain of the user
        :type domain: str
        :return: A tuple, the boolean True is the login is successful, the dict has extra info for the login/passwword policy 
        :rtype: tuple[bool, dict, dict]
        """
        logger.error("Method 'check_user_creds' of ClientUserSource must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError




    # update_user_creds: Update credentials of a user

    def get_user_info(self, uid:str, extra_condition:Condition, username:str, domain:str, password:str) -> dict[str, list[str]]:
        """
        Get info for a user or an empty dict if the user is not found/does not exist

        :param uid: _description_
        :type uid: str
        :param extra_condition: _description_
        :type extra_condition: Condition
        :param username: _description_
        :type username: str
        :param domain: _description_
        :type domain: str
        :param password: _description_
        :type password: str
        :return: _description_
        :rtype: dict[str, list[str]]
        """
        logger.error("Method 'get_user_info' of ClientUserSource must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    def search_user(self, search:str, extra_condition:Condition, limit:int, username:str, domain:str, password:str) -> Generator[dict[str, list[str]]]:
        """
        Search a user for autcompletion

        :param search: String to search
        :type search: str
        :param extra_condition: extra conditions for autocompletion
        :type extra_condition: Condition
        :return: infos of the user
        :rtype: dict[str, list[str]]
        """
        logger.error("Method 'search_user' of ClientUserSource must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    # get_all_users: get all users from this user source

