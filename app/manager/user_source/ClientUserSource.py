from abc import ABCMeta, abstractmethod
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

    # get_user_info: Get contact info a of user/resource/groups by uid

    # search_user: search user/resource/groups with search criteria

    # get_all_users: get all users from this user source

