from __future__ import annotations
from typing import TYPE_CHECKING

import requests
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.requests_client import OAuth2Session

from app.module.auth.identity_provider import IdentityProvider, IdentityProviderUserInfo
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_auth

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import AuthSettingsObj

OPENID_TIMEOUT = 10 #Timeout in seconds for every request made to the openid server


class OpenIDProvider(IdentityProvider):
    """
    OpenID Connect identity provider, authorization code flow.

    TODO state, nonce and pkce are not implemented yet.
    """

    kind = "openid"

    def __init__(self, auth_settings: AuthSettingsObj, callback_url: str):
        """
        Initialize the openid provider

        :param auth_settings: Authentication settings of the domain, SOGO_D_AUTH_TYPE must be 'openid'
        :type auth_settings: AuthSettingsObj
        :param callback_url: API url called by the openid server after the user logged in (redirect_uri)
        :type callback_url: str
        """
        super().__init__(auth_settings, callback_url)
        self._metadata: dict = {}

    def _get_config_url(self) -> dict:
        """
        Fetch the openid server configuration from the discovery url (SOGO_D_OPENID_CONFIG_URL)
        #TODO cache it

        :raises RequestException: If the openid server is unreachable or the configuration is invalid
        :return: The openid configuration
        :rtype: dict
        """
        if not self._metadata:
            config_url = self.auth_settings.SOGO_D_OPENID_CONFIG_URL
            try:
                response = requests.get(config_url, timeout=OPENID_TIMEOUT)
                response.raise_for_status()
                self._metadata = response.json()
            except (requests.RequestException, ValueError) as e:
                logger_auth.error("Cannot get openid configuration from %s: %s", config_url, str(e))
                raise RequestException(error=err.ERROR_SSO_PROVIDER_UNREACHABLE) from e
        return self._metadata

    def _get_endpoint(self, name: str) -> str:
        """
        Return an endpoint from the openid configuration

        :param name: Name of the endpoint in the configuration (authorization_endpoint, token_endpoint...)
        :type name: str
        :raises RequestException: If the endpoint is missing from the configuration
        :return: The endpoint url
        :rtype: str
        """
        print('######## FETCHING OPENID ENDPOINT ########')
        endpoint = self._get_config_url().get(name)
        print(f"Resolved endpoint for '{name}': {endpoint}")
        if not endpoint:
            logger_auth.error("Openid configuration from %s has no %s", self.auth_settings.SOGO_D_OPENID_CONFIG_URL, name)
            raise RequestException(error=err.ERROR_SSO_PROVIDER_UNREACHABLE)
        return endpoint

    def _get_client(self) -> OAuth2Session:
        """
        Return the oauth2 client for this domain

        :return: The oauth2 client
        :rtype: OAuth2Session
        """
        return OAuth2Session(client_id=self.auth_settings.SOGO_D_OPENID_CLIENT_NAME,
                             client_secret=self.auth_settings.SOGO_D_OPENID_CLIENT_SECRET,
                             scope=self.auth_settings.SOGO_D_OPENID_SCOPE,
                             redirect_uri=self.callback_url,
                             default_timeout=OPENID_TIMEOUT)

    def get_login_location(self) -> str:
        """
        Return the authorization url of the openid server

        :return: The authorization url
        :rtype: str
        """
        client = self._get_client()
        #TODO state, nonce and pkce. An empty state is not added to the url by authlib.
        url, _ = client.create_authorization_url(self._get_endpoint("authorization_endpoint"), state="")
        return url

    def authenticate_from_callback(self, callback_data: dict) -> IdentityProviderUserInfo:
        """
        Exchange the authorization code against an access token, then fetch the user info

        :param callback_data: Query parameters of the callback (code, or error and error_description)
        :type callback_data: dict
        :raises RequestException: If the authentication failed
        :return: The user identity
        :rtype: IdentityProviderUserInfo
        """
        print('################### CALLBACK OPENID ###################')
        if "error" in callback_data:
            logger_auth.info("Openid server returned an error: %s - %s",
                             callback_data["error"], callback_data.get("error_description", ""))
            raise RequestException(error=err.ERROR_SSO_LOGIN_FAILED)

        code = callback_data.get("code")
        print(f"Authorization code received: {code}")
        if not code:
            raise RequestException("No authorization code given in openid callback", err.ERROR_SSO_LOGIN_FAILED)

        #TODO check state
        client = self._get_client()
        try:
            print("Fetching access token from openid server...")
            print("______________________________")
            client.fetch_token(self._get_endpoint("token_endpoint"), code=code)
        except AuthlibBaseError as e:
            logger_auth.info("Openid server refused the authorization code: %s", str(e))
            raise RequestException(error=err.ERROR_SSO_LOGIN_FAILED) from e
        except requests.RequestException as e:
            logger_auth.error("Cannot get access token from openid server: %s", str(e))
            raise RequestException(error=err.ERROR_SSO_PROVIDER_UNREACHABLE) from e

        if not self.auth_settings.SOGO_D_OPENID_FETCH_USER_PROFILE:
            #TODO validate the id_token (jwks, nonce) and read the claims from it
            raise RequestException("SOGO_D_OPENID_FETCH_USER_PROFILE=False is not implemented yet", err.ERROR_SSO_LOGIN_FAILED)

        try:
            response = client.get(self._get_endpoint("userinfo_endpoint"))
            response.raise_for_status()
            user_info: dict = response.json()
        except (requests.RequestException, ValueError) as e:
            logger_auth.error("Cannot get user info from openid server: %s", str(e))
            raise RequestException(error=err.ERROR_SSO_PROVIDER_UNREACHABLE) from e

        mail_field = self.auth_settings.SOGO_D_OPENID_EMAIL
        mail = user_info.get(mail_field)
        if not mail or not isinstance(mail, str):
            logger_auth.warning("Openid user info has no field %s (see SOGO_D_OPENID_EMAIL)", mail_field)
            raise RequestException(error=err.ERROR_SSO_LOGIN_FAILED)
        print(f"Email retrieved: {mail}")
        print(f"User info retrieved: {user_info}")
        return IdentityProviderUserInfo(mail=mail, claims=user_info)
