from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import AuthSettingsObj


@dataclass
class IdentityProviderUserInfo:
    """
    Identity of a user, as returned by an identity provider after a successful authentication
    """
    mail: str #Mail of the user, used to match the user in the user sources
    claims: dict = field(default_factory=dict) #Raw data given by the identity provider (openid user info, saml attributes...)
    access_token: str = "" #Token given by the identity provider, used to authenticate on the mail servers (xoauth2)


class IdentityProvider(ABC):
    """
    Abstract class for all SSO identity providers (openid, saml...).

    The flow is always the same:
    1. get_login_location: url where the UI must send the user to log in
    2. The identity provider calls back the API (see /auth/callback/<kind>/<domain>)
    3. authenticate_from_callback: check the callback data and return the user identity
    """

    kind: str = "" #Must match SOGO_D_AUTH_TYPE

    def __init__(self, auth_settings: AuthSettingsObj, callback_url: str):
        """
        Initialize the identity provider

        :param auth_settings: Authentication settings of the domain
        :type auth_settings: AuthSettingsObj
        :param callback_url: API url called by the identity provider after the user logged in
        :type callback_url: str
        """
        self.auth_settings = auth_settings
        self.callback_url = callback_url

    @abstractmethod
    def get_login_location(self, state: str) -> str:
        """
        Return the url of the identity provider where the user must log in

        :param state: Opaque value the identity provider must send back on the callback (anti CSRF)
        :type state: str
        :return: The login url
        :rtype: str
        """

    @abstractmethod
    def authenticate_from_callback(self, callback_data: dict) -> IdentityProviderUserInfo:
        """
        Check the data sent by the identity provider on the callback and return the user identity

        :param callback_data: Data received on the callback (query parameters, form...)
        :type callback_data: dict
        :raises RequestException: If the authentication failed
        :return: The user identity
        :rtype: IdentityProviderUserInfo
        """
