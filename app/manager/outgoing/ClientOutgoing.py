from __future__ import annotations

from abc import ABCMeta, abstractmethod
from email.message import Message


class ClientOutgoing(metaclass=ABCMeta):
    """
    Abstract class for outgoing mail clients.
    All outgoing mail clients should inherit from this class and implement its methods.
    """

    def __init__(self) -> None:
        self.connected = False
        self.authenticated = False

    @abstractmethod
    def connect(self) -> None:
        """Open connection with the outgoing mail server."""

    @abstractmethod
    def login(self, username: str, password: str, authname: str = "") -> None:
        """Authenticate the user to the outgoing mail server."""

    @abstractmethod
    def send_mail(self, message: Message) -> None:
        """Send a mail."""
