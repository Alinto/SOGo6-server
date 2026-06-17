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
        """
        Login to the outgoing mail server.

        The param authname is only use for PLAIN method (authzid)
        https://datatracker.ietf.org/doc/html/rfc4616#section-2
        In means that username will act as authname. Can be useful to
        make admin operation and user.

        :param username: the username to use
        :type username: str
        :param password: the password in plain text to use
        :type password: str
        :param authname: authzid of PLAIN SASL, defaults to ""
        :type authname: str, optional
        """

    @abstractmethod
    def send_mail(self, message: Message) -> None:
        """Send a mail."""
