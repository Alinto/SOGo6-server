"""
Integration tests of the request hooks of create_app with MFA vouchers:
an MFA voucher only reaches the endpoints of its stage and is never a user session.
Database and cache are faked; the interfaces behind the MFA endpoints are faked too.
"""
import pytest

from app.api import create_app as create_app_module
from app.api.create_app import create_app
from app.auth.User import User
from app.auth.service import VoucherMfaService as voucher_mfa_module
from app.auth.service import VoucherUserService as voucher_user_module
from app.auth.service.VoucherMfaService import VoucherMfaService
from app.config.settings.ProcessSetting import process_config
from app.utils import constants as cs
from app.utils import errors as err

from tests._mfa_fakes import FakeCache

BASE = "/api/user/v1"


class FakeInterfaceAuthUser:
    """Replaces InterfaceAuthUser in the Auth blueprint."""
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    def mfa_verify(self, mfa_session, code, ip):
        FakeInterfaceAuthUser.calls.append(("mfa_verify", mfa_session.uid, code))
        return {"data": {"jwt_token": "user-voucher"}}, 200

    def plain_login(self, data, voucher_data, ip):
        FakeInterfaceAuthUser.calls.append(("plain_login", data["username"]))
        return {"data": {"jwt_token": "user-voucher"}}, 200


class FakeInterfaceUserMfa:
    """Replaces InterfaceUserMfa in the Mfa blueprint."""
    calls: list = []

    def __init__(self, process_settings, user_domain, user, mfa_session=None):
        self.mfa_session = mfa_session

    def begin_enrollment(self, provider, code, ip):
        FakeInterfaceUserMfa.calls.append(("begin", self.mfa_session.stage if self.mfa_session else None))
        return {"data": {"otpauth_uri": "otpauth://totp/x"}}, 200, {"Cache-Control": "no-store"}

    def confirm_enrollment(self, code, ip):
        FakeInterfaceUserMfa.calls.append(("confirm", self.mfa_session.stage if self.mfa_session else None))
        return {"data": {"jwt_token": "user-voucher"}}, 200

    def get_status(self):
        FakeInterfaceUserMfa.calls.append(("status", None))
        return {"data": {}}, 200

    def disable(self, code, ip):
        FakeInterfaceUserMfa.calls.append(("disable", None))
        return {"data": {}}, 200


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(voucher_mfa_module, "sogo_cache", lambda: fake)
    monkeypatch.setattr(voucher_user_module, "sogo_cache", lambda: fake)
    return fake


@pytest.fixture
def client(monkeypatch, cache):
    monkeypatch.setattr(create_app_module, "init_get_system_and_default_domain_settings", lambda: ({}, {}))
    domains = []
    def fake_domain_settings(domain, default):
        domains.append(domain)
        return {"AUTH_SETTINGS": {}}
    monkeypatch.setattr(create_app_module, "init_get_domain_settings", fake_domain_settings)
    monkeypatch.setattr("app.api.v1.auth.AuthUserApi.InterfaceAuthUser", FakeInterfaceAuthUser)
    monkeypatch.setattr("app.api.v1.user.ApiUserMfa.InterfaceUserMfa", FakeInterfaceUserMfa)
    FakeInterfaceAuthUser.calls = []
    FakeInterfaceUserMfa.calls = []
    app = create_app(cs.SOGO_OK)
    app.testing = True
    test_client = app.test_client()
    test_client.domains = domains
    return test_client


def mfa_token(stage: str) -> str:
    user = User("alice@example.com", "s3cret", domain="example.com")
    user.mail = "alice@example.com"
    return VoucherMfaService(process_config).create(user, stage, provider="totp" if stage == cs.MFA_STAGE_VERIFY else "")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_verify_token_reaches_mfa_verify(client):
    resp = client.post(f"{BASE}/auth/mfa/verify", json={"code": "123456"}, headers=bearer(mfa_token(cs.MFA_STAGE_VERIFY)))
    assert resp.status_code == 200
    assert FakeInterfaceAuthUser.calls == [("mfa_verify", "alice@example.com", "123456")]
    #The settings of the user's domain are loaded for the MFA endpoints
    assert client.domains == ["example.com"]


def test_mfa_verify_without_token(client):
    resp = client.post(f"{BASE}/auth/mfa/verify", json={"code": "123456"})
    assert resp.status_code == 401
    assert resp.get_json()["error_code"] == err.ERROR_AUTHENTICATED_ROUTE.c
    assert FakeInterfaceAuthUser.calls == []


def test_expired_mfa_session(client, cache):
    token = mfa_token(cs.MFA_STAGE_VERIFY)
    cache.hashes.clear()
    resp = client.post(f"{BASE}/auth/mfa/verify", json={"code": "123456"}, headers=bearer(token))
    assert resp.status_code == 401
    assert resp.get_json()["error_code"] == err.ERROR_MFA_SESSION_INVALID.c
    assert FakeInterfaceAuthUser.calls == []


@pytest.mark.parametrize("method,path", [
    ("get", "/preferences"),
    ("get", "/profile"),
    ("get", "/mfa"),
    ("post", "/mfa"),
    ("post", "/mfa/confirm"),
    ("delete", "/mfa"),
    ("post", "/auth/logout"),
])
def test_verify_token_refused_elsewhere(client, method, path):
    resp = getattr(client, method)(f"{BASE}{path}", json={"code": "123456"}, headers=bearer(mfa_token(cs.MFA_STAGE_VERIFY)))
    assert resp.status_code == 401
    assert resp.get_json()["error_code"] == err.ERROR_AUTHENTICATED_ROUTE.c
    assert FakeInterfaceUserMfa.calls == []


def test_enroll_token_reaches_begin_and_confirm(client):
    token = mfa_token(cs.MFA_STAGE_ENROLL)
    resp = client.post(f"{BASE}/mfa", json={}, headers=bearer(token))
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    resp = client.post(f"{BASE}/mfa/confirm", json={"code": "123456"}, headers=bearer(token))
    assert resp.status_code == 200
    assert FakeInterfaceUserMfa.calls == [("begin", cs.MFA_STAGE_ENROLL), ("confirm", cs.MFA_STAGE_ENROLL)]


@pytest.mark.parametrize("method,path", [
    ("get", "/mfa"),
    ("delete", "/mfa"),
    ("post", "/auth/mfa/verify"),
    ("get", "/preferences"),
])
def test_enroll_token_refused_elsewhere(client, method, path):
    resp = getattr(client, method)(f"{BASE}{path}", json={"code": "123456"}, headers=bearer(mfa_token(cs.MFA_STAGE_ENROLL)))
    assert resp.status_code == 401
    assert FakeInterfaceUserMfa.calls == []
    assert FakeInterfaceAuthUser.calls == []


def test_login_still_reachable_with_a_stale_mfa_token(client, cache):
    token = mfa_token(cs.MFA_STAGE_VERIFY)
    cache.hashes.clear()
    resp = client.post(f"{BASE}/auth/login", json={"username": "alice@example.com", "password": "x"}, headers=bearer(token))
    assert resp.status_code == 200
    assert FakeInterfaceAuthUser.calls == [("plain_login", "alice@example.com")]
