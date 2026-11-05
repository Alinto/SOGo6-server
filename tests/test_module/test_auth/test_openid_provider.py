"""
Unit tests for OpenIDProvider. The openid server and redis are mocked.
"""
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from redis import exceptions as rexc
from flask import Flask

from app.module.auth import OpenIDProvider as op
from app.module.auth.OpenIDProvider import OpenIDProvider
from app.utils.exceptions import RequestException
from app.utils import constants as cs
from app.utils import errors as err

CALLBACK_URL = "http://127.0.0.1:5000/api/user/v1/auth/callback/openid/example.com"
OTHER_CALLBACK_URL = "http://127.0.0.1:5000/api/user/v1/auth/callback/openid/other.com"
UI_REDIRECT = "http://localhost:3001/en/auth/login/sso"
METADATA = {
    "issuer": "http://idp",
    "authorization_endpoint": "http://idp/auth",
    "token_endpoint": "http://idp/token",
    "userinfo_endpoint": "http://idp/userinfo",
}


class FakeAuthSettings:
    """Fake AuthSettingsObj for openid."""
    def __init__(self, fetch_user_profile=True, token_check_interval=0):
        self.SOGO_D_AUTH_TYPE = "openid"
        self.SOGO_D_OPENID_CONFIG_URL = "http://idp/.well-known/openid-configuration"
        self.SOGO_D_OPENID_CLIENT_NAME = "myClient"
        self.SOGO_D_OPENID_CLIENT_SECRET = "secret"
        self.SOGO_D_OPENID_SCOPE = "openid profile email"
        self.SOGO_D_OPENID_EMAIL = "email"
        self.SOGO_D_OPENID_FETCH_USER_PROFILE = fetch_user_profile
        self.SOGO_D_OPENID_TOKEN_CHECK_INTERVAL = token_check_interval


class FakeCache:
    """Fake ClientRedis, the TTL is only recorded"""
    def __init__(self):
        self.data: dict = {}
        self.ttl: dict = {}
        self.down = False #Simulate an unreachable redis

    def _check(self):
        if self.down:
            raise rexc.ConnectionError("down")

    def set(self, key, value, ttl, nx=False):
        self._check()
        self.data[key] = value
        self.ttl[key] = ttl
        return True

    def get(self, key, expected_type):
        self._check()
        return self.data.get(key)

    def pop(self, key, expected_type):
        self._check()
        return self.data.pop(key, None)

    def close(self):
        pass


@pytest.fixture
def app():
    """Flask app, without secret key: the flask session must not be used"""
    return Flask(__name__)


@pytest.fixture
def cache(monkeypatch):
    """Mock redis"""
    fake_cache = FakeCache()
    monkeypatch.setattr(op, "sogo_cache", lambda: fake_cache)
    return fake_cache


@pytest.fixture
def idp(monkeypatch, cache):
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


def state_key(state, callback_url=CALLBACK_URL) -> str:
    return f"{cs.SSO_STATE_KEY_PREFIX}openid:{callback_url}:{state}"


def login(app, callback_url=CALLBACK_URL) -> dict:
    """Call get_login_location, return the query of the authorization url"""
    with app.test_request_context("/auth/mode"):
        url = OpenIDProvider(FakeAuthSettings(), callback_url).get_login_location(UI_REDIRECT)
        return parse_qs(urlparse(url).query)


def callback(app, query_string: dict, callback_url=CALLBACK_URL, fetch_user_profile=True, providers: list|None = None):
    """Call authenticate_from_callback with this query string, return the identity. The provider is added to providers."""
    with app.test_request_context("/auth/callback", query_string=query_string):
        provider = OpenIDProvider(FakeAuthSettings(fetch_user_profile), callback_url)
        if providers is not None:
            providers.append(provider)
        return provider.authenticate_from_callback(query_string)


def test_get_login_location(app, idp, cache):
    """Authorization url has the client info, a state and a nonce, both kept in redis with the UI url"""
    with app.test_request_context("/auth/mode"):
        url = OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location(UI_REDIRECT)

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
    key = state_key(state)
    assert cache.data == {key: {"redirect_uri": CALLBACK_URL, "nonce": query["nonce"][0], cs.SSO_STATE_UI_REDIRECT: UI_REDIRECT}}
    assert cache.ttl[key] == cs.SSO_STATE_TTL


def test_get_login_location_state_is_random(app, idp):
    """Each login has its own state"""
    query1 = login(app)
    query2 = login(app)
    assert query1["state"] != query2["state"]


def test_get_login_location_idp_unreachable(app, monkeypatch):
    """Discovery url not reachable"""
    def fail(self):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", fail)

    with app.test_request_context("/auth/mode"), pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location(UI_REDIRECT)
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_authenticate_from_callback(app, idp, cache):
    """State is checked and consumed, code is exchanged and the mail is read from user info"""
    query = login(app)
    providers: list = []

    identity = callback(app, {"code": "abc", "state": query["state"][0]}, providers=providers)

    assert providers[0].ui_redirect == UI_REDIRECT
    assert identity.mail == "user@example.com"
    assert identity.claims["name"] == "John Doe"
    assert identity.access_token == "at"
    assert idp["fetch_token"] == [{"code": "abc", "state": query["state"][0], "redirect_uri": CALLBACK_URL}]
    assert idp["parse_id_token"] == query["nonce"]
    assert cache.data == {}


def test_authenticate_from_callback_id_token_claims(app, idp):
    """SOGO_D_OPENID_FETCH_USER_PROFILE=False: the mail is read from the validated id_token"""
    query = login(app)

    identity = callback(app, {"code": "abc", "state": query["state"][0]}, fetch_user_profile=False)

    assert identity.mail == "id@example.com"


def test_authenticate_from_callback_replay(app, idp):
    """The state is single use, the same callback can't be replayed"""
    query = login(app)
    query_string = {"code": "abc", "state": query["state"][0]}
    callback(app, query_string)

    with pytest.raises(RequestException) as e:
        callback(app, query_string)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE
    assert len(idp["fetch_token"]) == 1


@pytest.mark.parametrize("state", [None, "", "unknown"])
def test_authenticate_from_callback_invalid_state(app, idp, cache, state):
    """No state, empty state or state not in redis (forged)"""
    login(app)
    query_string = {"code": "abc"} if state is None else {"code": "abc", "state": state}

    with pytest.raises(RequestException) as e:
        callback(app, query_string)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE
    assert idp["fetch_token"] == []
    assert len(cache.data) == 1 #The real state is untouched


def test_authenticate_from_callback_other_domain(app, idp, cache):
    """State created for the callback of another domain"""
    query = login(app, OTHER_CALLBACK_URL)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]})
    assert e.value.error == err.ERROR_SSO_INVALID_STATE
    assert state_key(query["state"][0], OTHER_CALLBACK_URL) in cache.data


def test_authenticate_from_callback_expired_state(app, idp, cache):
    """State older than cs.SSO_STATE_TTL, removed by redis"""
    query = login(app)
    cache.data.clear()

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]})
    assert e.value.error == err.ERROR_SSO_INVALID_STATE


@pytest.mark.parametrize("query_string", [{}, {"error": "access_denied", "error_description": "no"}])
def test_authenticate_from_callback_no_code(app, idp, cache, query_string):
    """Error or missing code in callback: the state is consumed and the UI url known to send the error back"""
    query = login(app)
    providers: list = []

    with pytest.raises(RequestException) as e:
        callback(app, {**query_string, "state": query["state"][0]}, providers=providers)
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED
    assert idp["fetch_token"] == []
    assert providers[0].ui_redirect == UI_REDIRECT
    assert cache.data == {}


def test_authenticate_from_callback_error_invalid_state(app, idp, cache):
    """Error in callback with an unknown state: the UI url is unknown"""
    login(app)
    providers: list = []

    with pytest.raises(RequestException) as e:
        callback(app, {"error": "access_denied", "state": "unknown"}, providers=providers)
    assert e.value.error == err.ERROR_SSO_INVALID_STATE
    assert providers[0].ui_redirect == ""
    assert len(cache.data) == 1


def test_authenticate_from_callback_failure_keeps_ui_redirect(app, idp, monkeypatch):
    """The state is read, then the code exchange fails: the UI url is known to send the error back"""
    def fail(self, **kwargs):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.FlaskOAuth2App, "fetch_access_token", fail)
    query = login(app)
    providers: list = []

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]}, providers=providers)
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE
    assert providers[0].ui_redirect == UI_REDIRECT


def test_authenticate_from_callback_no_mail(app, idp):
    """User info has no SOGO_D_OPENID_EMAIL field"""
    idp["userinfo"] = {"sub": "123"}
    query = login(app)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]})
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED


def test_get_login_location_redis_unreachable(app, idp, cache):
    """Redis down when saving the state"""
    cache.down = True

    with app.test_request_context("/auth/mode"), pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location(UI_REDIRECT)
    assert e.value.error == err.ERROR_SSO_STATE_STORAGE_UNREACHABLE


def test_authenticate_from_callback_redis_unreachable(app, idp, cache):
    """Redis down when reading the state on the callback"""
    query = login(app)
    cache.down = True

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]})
    assert e.value.error == err.ERROR_SSO_STATE_STORAGE_UNREACHABLE
    assert idp["fetch_token"] == []


# ========== Tests for check_access_token ==========

class FakeResponse:
    """Fake requests response"""
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


@pytest.fixture
def token_server(monkeypatch, idp):
    """Mock the introspection and userinfo endpoints, return the calls made to them"""
    calls = {"introspect": [], "userinfo": [], "introspect_response": FakeResponse(json_data={"active": True}),
             "userinfo_response": FakeResponse()}

    def fake_post(url, data, auth, timeout):
        calls["introspect"].append({"url": url, "data": data, "auth": auth})
        return calls["introspect_response"]

    def fake_get(url, headers, timeout):
        calls["userinfo"].append({"url": url, "headers": headers})
        return calls["userinfo_response"]

    monkeypatch.setattr(op.requests, "post", fake_post)
    monkeypatch.setattr(op.requests, "get", fake_get)
    return calls


def with_introspection(monkeypatch):
    """The openid server has an introspection endpoint"""
    metadata = dict(METADATA, introspection_endpoint="http://idp/introspect")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", lambda self: metadata)


@pytest.mark.parametrize("active, expected", [(True, True), (False, False), (None, False)])
def test_check_access_token_introspection(monkeypatch, token_server, cache, active, expected):
    """The introspection endpoint is used with the client credentials, the token is valid only if active is true"""
    with_introspection(monkeypatch)
    token_server["introspect_response"] = FakeResponse(json_data={} if active is None else {"active": active})

    assert OpenIDProvider(FakeAuthSettings(), "").check_access_token("at") is expected
    assert token_server["introspect"] == [{"url": "http://idp/introspect",
                                           "data": {"token": "at", "token_type_hint": "access_token"},
                                           "auth": ("myClient", "secret")}]
    assert token_server["userinfo"] == []
    assert cache.data == {}


@pytest.mark.parametrize("status_code, expected", [(200, True), (401, False), (403, False)])
def test_check_access_token_userinfo(token_server, status_code, expected):
    """No introspection endpoint: the token is valid if the userinfo endpoint accepts it"""
    token_server["userinfo_response"] = FakeResponse(status_code=status_code)

    assert OpenIDProvider(FakeAuthSettings(), "").check_access_token("at") is expected
    assert token_server["userinfo"] == [{"url": "http://idp/userinfo", "headers": {"Authorization": "Bearer at"}}]


def test_check_access_token_empty(token_server):
    """No token, nothing is asked to the openid server"""
    assert not OpenIDProvider(FakeAuthSettings(), "").check_access_token("")
    assert token_server["userinfo"] == []


@pytest.mark.parametrize("response", [FakeResponse(status_code=500), FakeResponse(status_code=502)])
def test_check_access_token_server_error(token_server, response):
    """The openid server answered an error that does not say the token is invalid"""
    token_server["userinfo_response"] = response

    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), "").check_access_token("at")
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_check_access_token_idp_unreachable(monkeypatch, cache):
    """Discovery url not reachable"""
    def fail(self):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", fail)

    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), "").check_access_token("at")
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_check_access_token_interval(token_server, cache):
    """Once valid, the token is not checked again during SOGO_D_OPENID_TOKEN_CHECK_INTERVAL, the token is not in redis"""
    provider = OpenIDProvider(FakeAuthSettings(token_check_interval=300), "")

    assert provider.check_access_token("at")
    assert provider.check_access_token("at")
    assert len(token_server["userinfo"]) == 1
    [key] = cache.data
    assert key.startswith(f"{cs.SSO_TOKEN_CHECK_KEY_PREFIX}openid:")
    assert "at" not in key.removeprefix(f"{cs.SSO_TOKEN_CHECK_KEY_PREFIX}openid:")
    assert cache.ttl[key] == 300

    #Another token is checked
    assert provider.check_access_token("other")
    assert len(token_server["userinfo"]) == 2


def test_check_access_token_interval_invalid_not_cached(token_server, cache):
    """An invalid token is never kept as checked"""
    token_server["userinfo_response"] = FakeResponse(status_code=401)

    assert not OpenIDProvider(FakeAuthSettings(token_check_interval=300), "").check_access_token("at")
    assert cache.data == {}


def test_check_access_token_interval_redis_unreachable(token_server, cache):
    """Redis down: the token is checked on the openid server every time"""
    cache.down = True
    provider = OpenIDProvider(FakeAuthSettings(token_check_interval=300), "")

    assert provider.check_access_token("at")
    assert provider.check_access_token("at")
    assert len(token_server["userinfo"]) == 2
