

class LoginPolicy:
    """
    Class to stores data from login policy (grace, expired...)
    """

    def __init__(self, error: str = "", grace: int = 0, expired: int = 0, tentative: int = 0):
        """
        NOT IMPLEMENTED

        :param error: _description_, defaults to ""
        :type error: str, optional
        :param grace: _description_, defaults to 0
        :type grace: int, optional
        :param expired: _description_, defaults to 0
        :type expired: int, optional
        :param tentative: _description_, defaults to 0
        :type tentative: int, optional
        """

        self.error = error
        self.grace = grace
        self.expired = expired
        self.tentative = tentative