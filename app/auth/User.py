from abc import ABCMeta, abstractmethod
from typing import Any

class User:
    """
    Reprensation of a User, can be anonymous
    """

    def __init__(self, username:str, domain:str|None: False, is_domainless:bool = False):
    
        pass

    def check_login(self):
        pass