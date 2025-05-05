# -*- coding: utf-8 -*-


class Prefs(dict):

    def __init__(self):
        # init with default value
        pass

    def init_with_user_id(self, user_id: str) -> None:
        # get a dict from the database
        data = {
            "language": "French"
        }
        self.update(data)

    def get_defaults_for_domain(self, domain: str|None) -> dict:
        """
        return the defaults for user's preferences for a domain
        """
        # get the default git from database (or cached here)
        data = {
            "language": "English"
        }
        return data

