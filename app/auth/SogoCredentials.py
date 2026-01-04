from abc import ABCMeta, abstractmethod
from typing import Any

class SogoCredentials(metaclass=ABCMeta):
    """
    Credentials in SOGo context, can be a token, username/password, else...
    """

    def __init__(self, process_settings: dict, system_settings: dict, domain_settings: dict):
        self.process_settings = process_settings
        self.system_settings  = system_settings
        self.domain_settings  = domain_settings

    @abstractmethod
    def get_creds(self) -> Any:
        """
        Return the needed data for this king of credential
        """


class BasicCredentials(SogoCredentials):
    """
    Sogo credentials basic, meaning a username and a password
    """
    def __init__(self,  process_settings: dict, system_settings: dict, domain_settings: dict, username:str, password:str):
        super().__init__(process_settings, system_settings, domain_settings)
        self.username = username
        self.password = password
    
    def get_creds(self) -> tuple[str,str]:
        """
        Return the needed data for this king of credential
        """
        return (self.username, self.password)

    def check_login(self) -> bool:
        """
        Get the user sources for this domain
        """
        ret = False

        return ret