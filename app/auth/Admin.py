"""
Admin user representation for authentication
"""


class Admin:
    """
    Represents an authenticated admin
    """

    def __init__(self, uid: str = "") -> None:
        """
        Initialize an Admin instance

        :param uid: Admin username/UID
        :type uid: str
        """
        self.uid = uid
        self.authenticated = True
        self.anonymous = False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(uid='{self.uid}')"


class AdminAnonymous(Admin):
    """
    Represents a non-authenticated admin (anonymous)
    """

    def __init__(self) -> None:
        super().__init__(uid="anonymous")
        self.authenticated = False
        self.anonymous = True
