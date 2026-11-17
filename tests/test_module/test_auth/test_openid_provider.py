"""
Unit tests for OpenIDProvider. The openid server and redis are mocked.
"""
from urllib.parse import urlparse, parse_qs
from hashlib import sha256
import base64
import json
import time

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
    def __init__(self, fetch_user_profile=True, token_check_interval=0, require_email_verified=True, endsession_enabled=False):
        self.SOGO_D_AUTH_TYPE = "openid"
        self.SOGO_D_OPENID_CONFIG_URL = "http://idp/.well-known/openid-configuration"
        self.SOGO_D_OPENID_CLIENT_NAME = "myClient"
        self.SOGO_D_OPENID_CLIENT_SECRET = "secret"
        self.SOGO_D_OPENID_SCOPE = "openid profile email"
        self.SOGO_D_OPENID_EMAIL = "email"
        self.SOGO_D_OPENID_FETCH_USER_PROFILE = fetch_user_profile
        self.SOGO_D_OPENID_TOKEN_CHECK_INTERVAL = token_check_interval
        self.SOGO_D_OPENID_REQUIRE_EMAIL_VERIFIED = require_email_verified
        self.SOGO_D_OPENID_ENDSESSION_ENABLED = endsession_enabled


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


@pytest.fixture(autouse=True)
def clear_metadata_cache():
    """The server metadata is cached in the process: each test starts without it"""
    op.server_metadata_cache.clear()
    yield
    op.server_metadata_cache.clear()


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
    calls = {"fetch_token": [], "parse_id_token": [], "load_server_metadata": 0,
             "userinfo": {"sub": "123", "email": "user@example.com", "email_verified": True, "name": "John Doe"},
             "id_token_claims": {"sub": "123", "email": "id@example.com", "email_verified": True}}

    def fake_load_server_metadata(self):
        calls["load_server_metadata"] += 1
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

    state = query["state"][0]
    assert len(state) >= 30 #authlib generate_token(30)
    key = state_key(state)
    code_verifier = cache.data[key]["code_verifier"]
    assert cache.data == {key: {"redirect_uri": CALLBACK_URL, "nonce": query["nonce"][0], "code_verifier": code_verifier,
                                cs.SSO_STATE_UI_REDIRECT: UI_REDIRECT}}
    assert cache.ttl[key] == cs.SSO_STATE_TTL

    #PKCE: only the challenge is sent, the verifier is kept in the state for the code exchange
    assert query["code_challenge_method"] == ["S256"]
    expected_challenge = base64.urlsafe_b64encode(sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [expected_challenge]
    assert code_verifier not in url


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
    [fetch_token] = idp["fetch_token"]
    assert fetch_token["code"] == "abc"
    assert fetch_token["state"] == query["state"][0]
    assert fetch_token["redirect_uri"] == CALLBACK_URL
    assert len(fetch_token["code_verifier"]) >= 43 #PKCE verifier sent with the code (RFC 7636)
    assert idp["parse_id_token"] == query["nonce"]
    assert identity.id_token == "jwt"
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

REAL_USERINFO = op.FlaskOAuth2App.userinfo #Replaced by the idp fixture for the login flow
BASIC_AUTH = "Basic " + base64.b64encode(b"myClient:secret").decode()


def http_response(status_code=200, json_data=None):
    """Real requests response, as authlib reads it"""
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = json.dumps(json_data if json_data is not None else {}).encode()
    resp.headers["Content-Type"] = "application/json"
    return resp


@pytest.fixture
def token_server(monkeypatch, idp):
    """
    Mock the http layer of requests: authlib really builds the requests to the userinfo, introspection and token endpoints.
    Return the calls made (form data and Authorization header), by endpoint.
    A response can be an exception, raised when sending the request.
    """
    endpoints = {"http://idp/userinfo": "userinfo", "http://idp/introspect": "introspect", "http://idp/token": "token",
                 "http://idp/revoke": "revoke"}
    calls = {"userinfo": [], "introspect": [], "token": [], "revoke": [], "revoke_response": http_response(),
             "userinfo_response": http_response(json_data={"email": "user@example.com"}),
             "introspect_response": http_response(json_data={"active": True}),
             "token_response": http_response(json_data={"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 300})}

    def fake_send(self, request, **kwargs):
        endpoint = endpoints[request.url]
        calls[endpoint].append({"method": request.method,
                                "data": {k: v[0] for k, v in parse_qs(request.body or "").items()},
                                "authorization": request.headers.get("Authorization"),
                                "timeout": kwargs.get("timeout")})
        response = calls[f"{endpoint}_response"]
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(op.FlaskOAuth2App, "userinfo", REAL_USERINFO)
    monkeypatch.setattr(requests.Session, "send", fake_send)
    return calls


def with_introspection(monkeypatch):
    """The openid server has an introspection endpoint"""
    metadata = dict(METADATA, introspection_endpoint="http://idp/introspect")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", lambda self: metadata)


@pytest.mark.parametrize("active, expected", [(True, True), (False, False), (None, False)])
def test_check_access_token_introspection(monkeypatch, token_server, cache, active, expected):
    """The introspection endpoint is used with the client credentials, the token is valid only if active is true"""
    with_introspection(monkeypatch)
    token_server["introspect_response"] = http_response(json_data={} if active is None else {"active": active})

    assert OpenIDProvider(FakeAuthSettings(), "").check_access_token("at") is expected
    assert token_server["introspect"] == [{"method": "POST",
                                           "data": {"token": "at", "token_type_hint": "access_token"},
                                           "authorization": BASIC_AUTH,
                                           "timeout": op.OPENID_TIMEOUT}]
    assert token_server["userinfo"] == []
    assert cache.data == {}


@pytest.mark.parametrize("status_code, expected", [(200, True), (401, False), (403, False)])
def test_check_access_token_userinfo(token_server, status_code, expected):
    """No introspection endpoint: the token is valid if the userinfo endpoint accepts it"""
    token_server["userinfo_response"] = http_response(status_code, {"email": "user@example.com"})

    assert OpenIDProvider(FakeAuthSettings(), "").check_access_token("at") is expected
    assert token_server["userinfo"] == [{"method": "GET", "data": {}, "authorization": "Bearer at", "timeout": op.OPENID_TIMEOUT}]


def test_check_access_token_empty(token_server):
    """No token, nothing is asked to the openid server"""
    assert not OpenIDProvider(FakeAuthSettings(), "").check_access_token("")
    assert token_server["userinfo"] == []


@pytest.mark.parametrize("response", [http_response(500), http_response(502), requests.ConnectionError("down")])
def test_check_access_token_server_error(token_server, response):
    """The openid server answered an error that does not say the token is invalid, or is unreachable"""
    token_server["userinfo_response"] = response

    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), "").check_access_token("at")
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_check_access_token_introspection_server_error(monkeypatch, token_server):
    """The introspection endpoint answered an error"""
    with_introspection(monkeypatch)
    token_server["introspect_response"] = http_response(500)

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
    token_server["userinfo_response"] = http_response(401)

    assert not OpenIDProvider(FakeAuthSettings(token_check_interval=300), "").check_access_token("at")
    assert cache.data == {}


def test_check_access_token_interval_redis_unreachable(token_server, cache):
    """Redis down: the token is checked on the openid server every time"""
    cache.down = True
    provider = OpenIDProvider(FakeAuthSettings(token_check_interval=300), "")

    assert provider.check_access_token("at")
    assert provider.check_access_token("at")
    assert len(token_server["userinfo"]) == 2


def test_authenticate_from_callback_keeps_refresh_token(app, idp, monkeypatch):
    """The refresh token and the expiration of the access token are given with the identity"""
    monkeypatch.setattr(op.FlaskOAuth2App, "fetch_access_token",
                        lambda self, **kwargs: {"access_token": "at", "refresh_token": "rt", "expires_at": 1234, "id_token": "jwt"})
    query = login(app)

    identity = callback(app, {"code": "abc", "state": query["state"][0]})

    assert (identity.access_token, identity.refresh_token, identity.expires_at) == ("at", "rt", 1234)


def test_authenticate_from_callback_without_refresh_token(app, idp):
    """No refresh token and no expiration given by the openid server"""
    query = login(app)
    identity = callback(app, {"code": "abc", "state": query["state"][0]})
    assert (identity.refresh_token, identity.expires_at) == ("", 0)


# ========== Tests for refresh_access_token ==========

def test_refresh_access_token(token_server):
    """grant_type=refresh_token on the token endpoint, client_secret_basic, scope sent again. The rotated refresh token is returned."""
    before = int(time.time())
    tokens = OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("rt")

    assert token_server["token"] == [{"method": "POST",
                                      "data": {"grant_type": "refresh_token", "refresh_token": "rt", "scope": "openid profile email"},
                                      "authorization": BASIC_AUTH,
                                      "timeout": op.OPENID_TIMEOUT}]
    assert (tokens.access_token, tokens.refresh_token) == ("new-at", "new-rt")
    assert before + 300 <= tokens.expires_at <= int(time.time()) + 300


def test_refresh_access_token_no_rotation(token_server):
    """No new refresh token given: the same one is kept. No expires_in: expiration unknown."""
    token_server["token_response"] = http_response(json_data={"access_token": "new-at", "token_type": "Bearer"})
    tokens = OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("rt")
    assert (tokens.access_token, tokens.refresh_token, tokens.expires_at) == ("new-at", "rt", 0)


@pytest.mark.parametrize("status_code, error", [(400, "invalid_grant"), (401, "invalid_client")])
def test_refresh_access_token_refused(token_server, status_code, error):
    """invalid_grant: the session ended on the openid server"""
    token_server["token_response"] = http_response(status_code, {"error": error, "error_description": "Session not active"})
    assert OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("rt") is None


def test_refresh_access_token_empty(token_server):
    """No refresh token: nothing to refresh, the openid server is not called"""
    assert OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("") is None
    assert token_server["token"] == []


@pytest.mark.parametrize("response", [http_response(500), http_response(json_data={"token_type": "Bearer"}),
                                      requests.ConnectionError("down")])
def test_refresh_access_token_server_error(token_server, response):
    """Server error, answer without access token, or unreachable: the refresh token may still be valid"""
    token_server["token_response"] = response
    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("rt")
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_refresh_access_token_non_json_error(token_server):
    """Error page that is not json (proxy, gateway...): not a refusal of the refresh token"""
    resp = http_response(401)
    resp._content = b"<html>Unauthorized</html>"
    token_server["token_response"] = resp
    with pytest.raises(RequestException) as e:
        OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("rt")
    assert e.value.error == err.ERROR_SSO_PROVIDER_UNREACHABLE


def test_refresh_access_token_new_id_token(token_server):
    """The openid server gave a new id_token with the refresh: it is returned, for the next logout"""
    token_server["token_response"] = http_response(json_data={"access_token": "new-at", "id_token": "new-jwt"})
    assert OpenIDProvider(FakeAuthSettings(), "").refresh_access_token("rt").id_token == "new-jwt"


# ========== Tests for the trust in the mail claim ==========

@pytest.mark.parametrize("email_verified", [False, "false", None, "missing"])
def test_authenticate_from_callback_email_not_verified(app, idp, email_verified):
    """SOGO_D_OPENID_REQUIRE_EMAIL_VERIFIED: a mail not verified by the openid server could be the mail of someone else"""
    for claims in (idp["userinfo"], idp["id_token_claims"]):
        if email_verified == "missing":
            claims.pop("email_verified")
        else:
            claims["email_verified"] = email_verified
    query = login(app)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]})
    assert e.value.error == err.ERROR_SSO_EMAIL_NOT_VERIFIED


@pytest.mark.parametrize("email_verified", [True, "true", "True"])
def test_authenticate_from_callback_email_verified(app, idp, email_verified):
    """Boolean, or string for some openid servers"""
    idp["userinfo"]["email_verified"] = email_verified
    query = login(app)
    assert callback(app, {"code": "abc", "state": query["state"][0]}).mail == "user@example.com"


def test_authenticate_from_callback_email_verified_from_id_token(app, idp):
    """The user info does not have email_verified: read from the validated id_token"""
    idp["userinfo"].pop("email_verified")
    query = login(app)
    assert callback(app, {"code": "abc", "state": query["state"][0]}).mail == "user@example.com"


def test_authenticate_from_callback_email_verified_not_required(app, idp):
    """SOGO_D_OPENID_REQUIRE_EMAIL_VERIFIED off (claim not editable by the users): not checked"""
    idp["userinfo"]["email_verified"] = False
    idp["id_token_claims"]["email_verified"] = False
    query = login(app)
    with app.test_request_context("/auth/callback", query_string={"code": "abc", "state": query["state"][0]}):
        provider = OpenIDProvider(FakeAuthSettings(require_email_verified=False), CALLBACK_URL)
        identity = provider.authenticate_from_callback({"code": "abc", "state": query["state"][0]})
    assert identity.mail == "user@example.com"


def test_authenticate_from_callback_userinfo_other_sub(app, idp):
    """OIDC Core 5.3.2: the user info must be about the user of the id_token"""
    idp["userinfo"]["sub"] = "456"
    query = login(app)

    with pytest.raises(RequestException) as e:
        callback(app, {"code": "abc", "state": query["state"][0]})
    assert e.value.error == err.ERROR_SSO_LOGIN_FAILED


# ========== Tests for the server metadata cache ==========

def test_server_metadata_cached(app, idp):
    """The discovery document is fetched once for all the providers of this openid server, until it expires"""
    login(app)
    login(app)
    assert idp["load_server_metadata"] == 1


def test_server_metadata_cache_expired(app, idp, monkeypatch):
    """Fetched again once cs.SSO_METADATA_TTL is over"""
    login(app)
    now = time.monotonic()
    monkeypatch.setattr(op.time, "monotonic", lambda: now + cs.SSO_METADATA_TTL + 1)
    login(app)
    assert idp["load_server_metadata"] == 2


def test_server_metadata_cache_by_url(app, idp):
    """Each openid server (SOGO_D_OPENID_CONFIG_URL) has its own metadata"""
    login(app)
    settings = FakeAuthSettings()
    settings.SOGO_D_OPENID_CONFIG_URL = "http://other-idp/.well-known/openid-configuration"
    with app.test_request_context("/auth/mode"):
        OpenIDProvider(settings, CALLBACK_URL).get_login_location(UI_REDIRECT)
    assert idp["load_server_metadata"] == 2


def test_server_metadata_not_cached_on_error(app, idp, monkeypatch):
    """An unreachable openid server is asked again on the next login"""
    def fail(self):
        idp["load_server_metadata"] += 1
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", fail)
    for _ in range(2):
        with app.test_request_context("/auth/mode"), pytest.raises(RequestException):
            OpenIDProvider(FakeAuthSettings(), CALLBACK_URL).get_login_location(UI_REDIRECT)
    assert idp["load_server_metadata"] == 2


def test_server_metadata_jwks_cached(monkeypatch):
    """The jwks fetched by authlib (validation of the id_token) are cached with the metadata"""
    op.server_metadata_cache.set("http://idp/.well-known/openid-configuration", dict(METADATA, _loaded_at=1))
    monkeypatch.setattr(op.FlaskOAuth2App, "fetch_jwk_set", lambda self, force=False: {"keys": ["k1"]})

    OpenIDProvider(FakeAuthSettings(), "")._client.fetch_jwk_set()
    assert op.server_metadata_cache.get("http://idp/.well-known/openid-configuration")["jwks"] == {"keys": ["k1"]}


# ========== Tests for logout ==========

LOGOUT_METADATA = dict(METADATA, revocation_endpoint="http://idp/revoke", end_session_endpoint="http://idp/logout")
POST_LOGOUT = "http://localhost:3001/en/auth/login"


def logout(monkeypatch, metadata=None, **settings):
    """Call logout with the tokens of a user, the openid server has these metadata"""
    metadata = LOGOUT_METADATA if metadata is None else metadata
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", lambda self: metadata)
    return OpenIDProvider(FakeAuthSettings(**settings), "").logout("at", "rt", "jwt", POST_LOGOUT)


def test_logout_revokes_tokens(monkeypatch, token_server):
    """RFC 7009: refresh token then access token, with the client credentials. No end session by default."""
    assert logout(monkeypatch) == ""
    assert token_server["revoke"] == [
        {"method": "POST", "data": {"token": "rt", "token_type_hint": "refresh_token"}, "authorization": BASIC_AUTH, "timeout": op.OPENID_TIMEOUT},
        {"method": "POST", "data": {"token": "at", "token_type_hint": "access_token"}, "authorization": BASIC_AUTH, "timeout": op.OPENID_TIMEOUT},
    ]


def test_logout_end_session(monkeypatch, token_server):
    """SOGO_D_OPENID_ENDSESSION_ENABLED: the url of the end_session_endpoint (RP-Initiated Logout) is returned"""
    location = logout(monkeypatch, endsession_enabled=True)

    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "http://idp/logout"
    assert query["id_token_hint"] == ["jwt"]
    assert query["post_logout_redirect_uri"] == [POST_LOGOUT]
    assert query["client_id"] == ["myClient"]
    assert len(token_server["revoke"]) == 2


def test_logout_end_session_without_redirect(monkeypatch, token_server):
    """No UI url: the openid server shows its own page"""
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", lambda self: LOGOUT_METADATA)
    location = OpenIDProvider(FakeAuthSettings(endsession_enabled=True), "").logout("at", "", "", "")
    query = parse_qs(urlparse(location).query)
    assert "post_logout_redirect_uri" not in query
    assert "id_token_hint" not in query
    assert query["client_id"] == ["myClient"]
    assert [call["data"]["token"] for call in token_server["revoke"]] == ["at"]


def test_logout_no_endpoints(monkeypatch, token_server):
    """No revocation endpoint and no end_session_endpoint: nothing to do on the openid server"""
    assert logout(monkeypatch, metadata=METADATA, endsession_enabled=True) == ""
    assert token_server["revoke"] == []


@pytest.mark.parametrize("response", [http_response(400, {"error": "unsupported_token_type"}), requests.ConnectionError("down")])
def test_logout_revoke_error(monkeypatch, token_server, response):
    """The revocation failed: only logged, the logout url is still returned"""
    token_server["revoke_response"] = response
    assert logout(monkeypatch, endsession_enabled=True).startswith("http://idp/logout?")


def test_logout_idp_unreachable(monkeypatch, cache):
    """Discovery url not reachable: the user is logged out of SOGo anyway"""
    def fail(self):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(op.FlaskOAuth2App, "load_server_metadata", fail)
    assert OpenIDProvider(FakeAuthSettings(endsession_enabled=True), "").logout("at", "rt", "jwt", POST_LOGOUT) == ""
