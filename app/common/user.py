# -*- coding: utf-8 -*-

"""The User"""

from enum import Enum


class StateUser(Enum):
    UNKNOWN = -1
    ANONYOUS = 0
    AUTHENTICATED = 1


class User:

    def __init__(self):
        _state: StateUser = StateUser.UNKNOWN
        user_id: str = None
        user_mail: str = None
        user_domain: str = None
        user_pwd: str = None

    def check_username(self, username: str) -> bool:
        """
        Return true is the username exist in the user source
        """

    def check_login(self, username: str, password: str) -> bool:
        """
        Return true if the username and password are correct
        """

