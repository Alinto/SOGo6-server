"""
Unit tests for OpenIDProvider. The openid server is mocked.
"""
from urllib.parse import urlparse, parse_qs

import pytest
import requests

from app.module.auth import openid_provider as op
from app.module.auth.openid_provider import OpenIDProvider
from app.utils.exceptions import RequestException
from app.utils import errors as err

CALLBACK_URL = "http://127.0.0.1:5000/api/user/v1/auth/callback/openid/example.com"
METADATA = {
    "authorization_endpoint": "http://idp/auth",
    "token_endpoint": "http://idp/token",
    "userinfo_endpoint": "http://idp/userinfo",
}


class FakeAuthSettings:
    """Fake AuthSettingsObj for openid."""
    def __init__(self):
        self.SOGO_D_AUTH_TYPE = "openid"
        self.SOGO_D_OPENID_CONFIG_URL = "http://idp/.well-known/openid-configuration"
        self.SOGO_D_OPENID_CLIENT_NAME = "myClient"
        self.SOGO_D_OPENID_CLIENT_SECRET = "secret"
        self.SOGO_D_OPENID_SCOPE = "openid profile email"
        self.SOGO_D_OPENID_EMAIL = "email"
        self.SOGO_D_OPENID_FETCH_USER_PROFILE = True


class FakeResponse:
    """Fake requests response."""
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"status {self.status}")

    def json(self):
        return self.data


@pytest.fixture
def idp(monkeypatch):
    """Mock the openid server, return the calls made to the token endpoint"""
    calls = {"fetch_token": [], "userinfo": {"email": "user@example.com", "name": "John Doe"}}
    monkeypatch.setattr(op.requests, "get", lambda url, timeout: FakeResponse(METADATA))

    def fake_fetch_token(self, url, **kwargs):
        calls["fetch_token"].append((url, kwargs))
        return {"access_token": "at", "token_type": "Bearer"}

    def fake_get(self, url, **kwargs):
        return FakeResponse(calls["userinfo"])

    monkeypatch.setattr(op.OAuth2Session, "fetch_token", fake_fetch_token)
    monkeypatch.setattr(op.OAuth2Session, "get", fake_get)
    return calls


def test_get_login_location(idp):
    """Authorization url has the client info and the state, no nonce/pkce"""
    url = OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location("my-state")

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == METADATA["authorization_endpoint"]
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["myClient"]
    assert query["redirect_uri"] == [CALLBACK_URL]
    assert query["scope"] == ["openid profile email"]
    assert query["state"] == ["my-state"]
    assert "nonce" not in query
    assert "code_challenge" not in query


def test_get_login_location_idp_unreachable(monkeypatch):
    """Discovery url not reachable"""
    def fail(url, timeout):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.requests, "get", fail)

    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location("my-state")
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_authenticate_from_callback(idp):
    """Code is exchanged and the mail is read from user info"""
    identity = OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).authenticate_from_callback({"code": "abc"})

    assert identity.mail == "user@example.com"
    assert identity.claims["name"] == "John Doe"
    assert idp["fetch_token"] == [(METADATA["token_endpoint"], {"code": "abc"})]


@pytest.mark.parametrize("callback_data", [{}, {"error": "access_denied", "error_description": "no"}])
def test_authenticate_from_callback_no_code(idp, callback_data):
    """Error or missing code in callback"""
    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).authenticate_from_callback(callback_data)
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED
    assert idp["fetch_token"] == []


def test_authenticate_from_callback_no_mail(idp):
    """User info has no SOGO_D_OPENID_EMAIL field"""
    idp["userinfo"] = {"sub": "123"}
    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).authenticate_from_callback({"code": "abc"})
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED
