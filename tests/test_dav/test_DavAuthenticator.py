"""Unit tests for DavAuthenticator - the auth interface, the login limiter and the settings are fakes."""

from base64 import b64encode
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.auth.User import User, UserAnonymous
from app.config.settings.DomainSettings import AuthSettings
from app.config.settings.SystemSettings import SystemSettings
from app.dav.DavAuthenticator import DavAuthenticator
from app.dav.model.DavRequest import DavRequest
from app.utils import errors as err
from app.utils.exceptions import RequestException

USER_DOMAIN = {AuthSettings.subparent: {"SOGO_D_AUTH_TYPE": "plain", "SOGO_D_LOGIN_CHECK_MAX_ATTEMPT": 5}}
OPENID_DOMAIN = {AuthSettings.subparent: {"SOGO_D_AUTH_TYPE": "openid"}}
CACHE = SimpleNamespace()
SYSTEM = {SystemSettings.subparent: {}}


class FakeInterfaceAuthUser:
    def __init__(self):
        self.result = True
        self.domain = None
        self.checked = []

    def check_user_and_fill_info(self, user):
        self.checked.append((user.uid, user.password))
        if not self.result:
            return False, UserAnonymous()
        filled = User(user.uid, user.password)
        filled.cn = "Alice"
        filled.authenticated = True
        if self.domain is not None:
            filled.domain = self.domain
        return True, filled


class FakeLoginLimiter:
    def __init__(self):
        self.blocked = False
        self.checked = []
        self.failures = []

    def check_not_blocked(self, login, auth_settings):
        self.checked.append((login, auth_settings.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT))
        if self.blocked:
            raise RequestException(error=err.ERROR_DAV_LOGIN_BLOCKED)

    def record_failure(self, login, password, auth_settings):
        self.failures.append((login, password, auth_settings.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT))


@pytest.fixture
def env():
    interface = FakeInterfaceAuthUser()
    limiter = FakeLoginLimiter()
    with (
        patch("app.dav.DavAuthenticator.InterfaceAuthUser", return_value=interface) as interface_class,
        patch("app.dav.DavAuthenticator.DavLoginLimiter", return_value=limiter) as limiter_class,
        patch("app.dav.DavAuthenticator.init_get_system_and_default_domain_settings", return_value=(SYSTEM, {})),
        patch("app.dav.DavAuthenticator.init_get_user_domain_settings", return_value=USER_DOMAIN),
    ):
        yield SimpleNamespace(
            interface=interface, interface_class=interface_class, limiter=limiter, limiter_class=limiter_class
        )


def _authenticator(require_secure=True):
    return DavAuthenticator(SimpleNamespace(), require_secure=require_secure)


def _request(credentials="alice@example.org:secret", secure=True):
    headers = {}
    if credentials is not None:
        headers["authorization"] = "Basic " + b64encode(credentials.encode("utf-8")).decode("ascii")
    return DavRequest(method="PROPFIND", path="", headers=headers, secure=secure)


# ========== Tests for the request checks ==========


def test_insecure_connection_refused(env):
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(_request(secure=False), CACHE)
    assert ex.value.error is err.ERROR_DAV_INSECURE_CONNECTION
    assert not env.interface.checked


def test_insecure_connection_allowed_in_dev(env):
    context = _authenticator(require_secure=False).authenticate(_request(secure=False), CACHE)
    assert context.user.authenticated


def test_missing_credentials(env):
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(_request(credentials=None), CACHE)
    assert ex.value.error is err.ERROR_AUTHENTICATED_ROUTE


@pytest.mark.parametrize("header", ["Bearer abc", "Basic !!!", "Basic " + b64encode(b"no-colon").decode("ascii")])
def test_malformed_credentials(env, header):
    request = DavRequest(method="PROPFIND", path="", headers={"authorization": header}, secure=True)
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(request, CACHE)
    assert ex.value.error is err.ERROR_WRONG_AUTHORIZATION_TYPE


def test_password_split_on_first_colon(env):
    _authenticator().authenticate(_request(credentials="alice@example.org:pa:ss"), CACHE)
    assert env.interface.checked == [("alice@example.org", "pa:ss")]


def test_empty_password_refused(env):
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(_request(credentials="alice@example.org:"), CACHE)
    assert ex.value.error is err.ERROR_LOGIN_FAILED
    assert not env.interface.checked


@pytest.mark.parametrize(
    "login",
    [
        "a*@example.org",
        "alice)(uid=*@example.org",
        "uid=alice,dc=org",
        "alice@example.org@other.org",
        "ali\x00ce@example.org",
        "alice\u200b@example.org",
        "alice@example.org ",
        "alice @example.org",
        "#616c696365@example.org",
    ],
)
def test_login_altering_queries_refused(env, login):
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(_request(credentials=login + ":secret"), CACHE)
    assert ex.value.error is err.ERROR_LOGIN_FAILED
    assert not env.interface.checked


@pytest.mark.parametrize(
    "system, login",
    [
        ({}, "alice"),
        ({"SOGO_S_REJECT_UNKNOWN_DOMAIN": True, "SOGO_S_KNOWN_DOMAIN": ["example.com"]}, "alice@example.org"),
    ],
)
def test_login_refused_by_domain_rules(env, system, login):
    with patch(
        "app.dav.DavAuthenticator.init_get_system_and_default_domain_settings",
        return_value=({SystemSettings.subparent: system}, {}),
    ):
        with pytest.raises(RequestException) as ex:
            _authenticator().authenticate(_request(credentials=login + ":secret"), CACHE)
    assert ex.value.error is err.ERROR_LOGIN_FAILED
    assert not env.interface.checked


def test_domainless_login_allowed(env):
    with patch(
        "app.dav.DavAuthenticator.init_get_system_and_default_domain_settings",
        return_value=({SystemSettings.subparent: {"SOGO_S_DOMAINLESS_LOGIN": True}}, {}),
    ):
        _authenticator().authenticate(_request(credentials="alice:secret"), CACHE)
    assert env.interface.checked == [("alice", "secret")]


def test_login_domain_lowered(env):
    _authenticator().authenticate(_request(credentials="Alice+tag@Example.ORG:secret"), CACHE)
    assert env.interface.checked == [("Alice+tag@example.org", "secret")]


# ========== Tests for the login limiter ==========


def test_blocked_login_refused(env):
    env.limiter.blocked = True
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(_request(), CACHE)
    assert ex.value.error is err.ERROR_DAV_LOGIN_BLOCKED
    assert not env.interface.checked


def test_wrong_password_recorded(env):
    env.interface.result = False
    with pytest.raises(RequestException) as ex:
        _authenticator().authenticate(_request(credentials="alice@Example.org:wrong"), CACHE)
    assert ex.value.error is err.ERROR_LOGIN_FAILED
    assert env.limiter.failures == [("alice@example.org", "wrong", 5)]


def test_right_password_not_recorded(env):
    _authenticator().authenticate(_request(), CACHE)
    assert env.limiter_class.call_args.args == (CACHE,)
    assert env.limiter.checked == [("alice@example.org", 5)]
    assert not env.limiter.failures


# ========== Tests for the user source check ==========


def test_context_with_filled_user(env):
    context = _authenticator().authenticate(_request(), CACHE)
    assert context.user.cn == "Alice"
    assert context.user.password == "secret"
    assert context.user_domain_settings is USER_DOMAIN
    assert context.cache is CACHE
    assert env.interface_class.call_args.kwargs["default_domain"] is USER_DOMAIN


def test_identity_provider_domain_refused(env):
    with patch("app.dav.DavAuthenticator.init_get_user_domain_settings", return_value=OPENID_DOMAIN):
        with pytest.raises(RequestException) as ex:
            _authenticator().authenticate(_request(), CACHE)
    assert ex.value.error is err.ERROR_DAV_PASSWORD_LOGIN_DISABLED
    assert not env.limiter.checked
    assert not env.interface.checked


def test_identity_provider_domain_of_account_refused(env):
    env.interface.domain = "sso.example.org"
    with patch(
        "app.dav.DavAuthenticator.init_get_user_domain_settings", side_effect=[USER_DOMAIN, OPENID_DOMAIN]
    ) as settings:
        with pytest.raises(RequestException) as ex:
            _authenticator().authenticate(_request(), CACHE)
    assert ex.value.error is err.ERROR_LOGIN_FAILED
    assert settings.call_args.args[0].domain == "sso.example.org"
    assert env.limiter.failures == [("alice@example.org", "secret", 5)]


def test_account_domain_reloaded_lowercased(env):
    env.interface.domain = "Other.Example.org"
    other_domain = {AuthSettings.subparent: {"SOGO_D_AUTH_TYPE": "plain"}}
    with patch(
        "app.dav.DavAuthenticator.init_get_user_domain_settings", side_effect=[USER_DOMAIN, other_domain]
    ) as settings:
        context = _authenticator().authenticate(_request(), CACHE)
    assert settings.call_args.args[0].domain == "other.example.org"
    assert context.user_domain_settings is other_domain


def test_account_domain_with_other_case_not_reloaded(env):
    env.interface.domain = "Example.org"
    with patch("app.dav.DavAuthenticator.init_get_user_domain_settings", return_value=USER_DOMAIN) as settings:
        _authenticator().authenticate(_request(), CACHE)
    assert settings.call_count == 1
