from abc import ABCMeta, abstractmethod
from typing import Any, Iterator

class ClientFiltering(metaclass=ABCMeta):
    """
    Abstract class for mail filtering clients.
    All filtering clients should inherit from this class and implement its methods.
    """
    def __init__(self) -> None:
        """
        Just set a param to tell if the client needs to authenticate or not
        """
        self.connected = False
        self.authenticated = False

    @abstractmethod
    def connect(self) -> None:
        """Connect to the mail server."""

    @abstractmethod
    def login(self, username: str, password: str) -> None:
        """Login to the mail server."""

    @abstractmethod
    def set_merged_filters(self, filters_config: dict) -> dict[str, bool]:
        """Set the merged filters on the mail server."""

    @abstractmethod
    def logout(self) -> None:
        """
        Disconnect from the mail filter server.
        """
