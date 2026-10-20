"""
Unit tests for OpenIDProvider. The openid server is mocked, the state is kept by authlib in the flask session.
"""
import time
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from flask import Flask, session

from app.module.auth import openid_provider as op
from app.module.auth.openid_provider import OpenIDProvider
from app.utils.exceptions import RequestException
from app.utils import constants as cs
from app.utils import errors as err

CALLBACK_URL = "http://127.0.0.1:5000/api/user/v1/auth/callback/openid/example.com"
OTHER_CALLBACK_URL = "http://127.0.0.1:5000/api/user/v1/auth/callback/openid/other.com"
METADATA = {
    "issuer": "http://idp",
    "authorization_endpoint": "http://idp/auth",
    "token_endpoint": "http://idp/token",
    "userinfo_endpoint": "http://idp/userinfo",
}


class FakeAuthSettings:
    """Fake AuthSettingsObj for openid."""
    def __init__(self, fetch_user_profile=True):
        self.SOGO_D_AUTH_TYPE = "openid"
        self.SOGO_D_OPENID_CONFIG_URL = "http://idp/.well-known/openid-configuration"
        self.SOGO_D_OPENID_CLIENT_NAME = "myClient"
        self.SOGO_D_OPENID_CLIENT_SECRET = "secret"
        self.SOGO_D_OPENID_SCOPE = "openid profile email"
        self.SOGO_D_OPENID_EMAIL = "email"
        self.SOGO_D_OPENID_FETCH_USER_PROFILE = fetch_user_profile


@pytest.fixture
def app():
    """Flask app with a secret key, needed by the flask session"""
    flask_app = Flask(__name__)
    flask_app.secret_key = "test"
    return flask_app


@pytest.fixture
def idp(monkeypatch):
    """Mock the openid server, return the calls made to it"""
    calls = {"fetch_token": [], "parse_id_token": [], "userinfo": {"email": "user@example.com", "name": "John Doe"},
             "id_token_claims": {"email": "id@example.com"}}

    def fake_load_server_metadata(self):
        return METADATA

    def fake_fetch_access_token(self, **kwargs):
        calls["fetch_token"].append(kwargs)
        return {"access_token": "at", "token_type": "Bearer", "id_token": "jwt"}

    def fake_parse_id_token(self, token, nonce, **kwargs):
        calls["parse_id_token"].append(nonce)
        return calls["id_token_claims"]

    def fake_userinfo(self):
        return calls["userinfo"]

    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", fake_load_server_metadata)
    monkeypatch.setattr(op.FlaskOAuth2App, "fetch_access_token", fake_fetch_access_token)
    monkeypatch.setattr(op.FlaskOAuth2App, "parse_id_token", fake_parse_id_token)
    monkeypatch.setattr(op.FlaskOAuth2App, "userinfo", fake_userinfo)
    return calls


def login(app, callback_url=CALLBACK_URL) -> tuple[dict, dict]:
    """Call get_login_location, return the query of the authorization url and the flask session"""
    with app.test_request_context("/auth/mode"):
        url = OpenIDProvider(FakeAuthSettings(), callback_url).get_login_location()
        return parse_qs(urlparse(url).query), dict(session)


def callback(app, query_string: dict, session_data: dict, callback_url=CALLBACK_URL, fetch_user_profile=True):
    """Call authenticate_from_callback with this query string and flask session, return the identity and the session after"""
    with app.test_request_context("/auth/callback", query_string=query_string):
        session.update(session_data)
        identity = OpenIDProvider(FakeAuthSettings(fetch_user_profile), callback_url).authenticate_from_callback(query_string)
        return identity, dict(session)


def test_get_login_location(app, idp):
    """Authorization url has the client info, a state and a nonce, both kept in the session"""
    with app.test_request_context("/auth/mode"):
        url = OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location()
        session_data = dict(session)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == METADATA["authorization_endpoint"]
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["myClient"]
    assert query["redirect_uri"] == [CALLBACK_URL]
    assert query["scope"] == ["openid profile email"]
    assert "code_challenge" not in query

    state = query["state"][0]
    assert len(state) >= 30 #authlib generate_token(30)
    stored = session_data[f"_state_openid:{CALLBACK_URL}_{state}"]
    assert stored["data"] == {"redirect_uri": CALLBACK_URL, "nonce": query["nonce"][0]}
    assert stored["exp"] == pytest.approx(time.time() + cs.SSO_STATE_TTL, abs=5)


def test_get_login_location_state_is_random(app, idp):
    """Each login has its own state"""
    query1, _ = login(app)
    query2, _ = login(app)
    assert query1["state"] != query2["state"]


def test_get_login_location_idp_unreachable(app, monkeypatch):
    """Discovery url not reachable"""
    def fail(self):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", fail)

    with app.test_request_context("/auth/mode"), pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location()
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_authenticate_from_callback(app, idp):
    """State is checked and consumed, code is exchanged and the mail is read from user info"""
    query, session_data = login(app)

    identity, session_after = callback(app, {"code": "abc", "state": query["state"][0]}, session_data)

    assert identity.mail == "user@example.com"
    assert identity.claims["name"] == "John Doe"
    assert identity.access_token == "at"
    assert idp["fetch_token"] == [{"code": "abc", "state": query["state"][0], "redirect_uri": CALLBACK_URL}]
    assert idp["parse_id_token"] == query["nonce"]
    assert session_after == {}


def test_authenticate_from_callback_id_token_claims(app, idp):
    """SOGO_D_OPENID_FETCH_USER_PROFILE=False: the mail is read from the validated id_token"""
    query, session_data = login(app)

    identity, _ = callback(app, {"code": "abc", "state": query["state"][0]}, session_data, fetch_user_profile=False)

    assert identity.mail == "id@example.com"


def test_authenticate_from_callback_replay(app, idp):
    """The state is single use, the same callback can't be replayed"""
    query, session_data = login(app)
    query_string = {"code": "abc", "state": query["state"][0]}
    _, session_after = callback(app, query_string, session_data)

    with pytest.raises(RequestException) as e:
        callback(app, query_string, session_after)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE
    assert len(idp["fetch_token"]) == 1


@pytest.mark.parametrize("state", [None, "", "unknown"])
def test_authenticate_from_callback_invalid_state(app, idp, state):
    """No state, empty state or state not in the session (forged)"""
    _, session_data = login(app)
    query_string = {"code": "abc"} if state is None else {"code": "abc", "state": state}

    with pytest.raises(RequestException) as e:
        callback(app, query_string, session_data)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE
    assert idp["fetch_token"] == []


def test_authenticate_from_callback_other_browser(app, idp):
    """Valid state but another session (login CSRF: the callback url of someone else)"""
    query, _ = login(app)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]}, {})
    assert e.value.error == err.ERROR_SSO_INVALID_STATE


def test_authenticate_from_callback_other_domain(app, idp):
    """State created for the callback of another domain"""
    query, session_data = login(app, OTHER_CALLBACK_URL)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]}, session_data)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE


def test_authenticate_from_callback_expired_state(app, idp):
    """State older than cs.SSO_STATE_TTL"""
    query, session_data = login(app)
    for value in session_data.values():
        value["exp"] = 0

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]}, session_data)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE


@pytest.mark.parametrize("query_string", [{}, {"error": "access_denied", "error_description": "no"}])
def test_authenticate_from_callback_no_code(app, idp, query_string):
    """Error or missing code in callback"""
    query, session_data = login(app)

    with pytest.raises(RequestException) as e:
        callback(app, {**query_string, "state": query["state"][0]}, session_data)
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED
    assert idp["fetch_token"] == []


def test_authenticate_from_callback_no_mail(app, idp):
    """User info has no SOGO_D_OPENID_EMAIL field"""
    idp["userinfo"] = {"sub": "123"}
    query, session_data = login(app)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]}, session_data)
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED
