"""
Unit tests for InterfaceUserMfa (Interface layer), with a fake ModuleMfa.
"""
import pytest

from app.auth.User import User, UserAnonymous
from app.interface.user.InterfaceUserMfa import InterfaceUserMfa
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException

DOMAIN = {"AUTH_SETTINGS": {"SOGO_D_LOGIN_MFA_METHOD": ["totp"]}}


class FakeModuleMfa:
    """Fake ModuleMfa recording its calls."""
    exception = None

    def __init__(self, process, auth_settings):
        self.auth_settings = auth_settings
        self.calls: list = []
        FakeModuleMfa.last = self

    def _maybe_raise(self):
        if FakeModuleMfa.exception is not None:
            raise FakeModuleMfa.exception

    def get_status(self, uid):
        self.calls.append(("get_status", uid))
        self._maybe_raise()
        return {"enabled": True, "method": None}

    def begin_enrollment(self, ctx, provider_id, current_code, ip):
        self.calls.append(("begin", ctx.uid, provider_id, current_code, ip))
        self._maybe_raise()
        return {"provider": "totp", "otpauth_uri": "otpauth://totp/x", "secret": "S"}

    def confirm_enrollment(self, ctx, code, ip, mfa_session):
        self.calls.append(("confirm", ctx.uid, code, ip, mfa_session))
        self._maybe_raise()
        return {"enabled": True, "method": {"provider": "totp"}}

    def finish_enrollment_login(self, mfa_session):
        self.calls.append(("finish", mfa_session))
        return {"jwt_token": "user-voucher"}

    def disable(self, ctx, code, ip):
        self.calls.append(("disable", ctx.uid, code, ip))
        self._maybe_raise()


class FakeMfaSession:
    def __init__(self, stage):
        self.uid = "bob@example.com"
        self.mail = "bob@example.com"
        self.stage = stage


@pytest.fixture(autouse=True)
def fake_module(monkeypatch):
    FakeModuleMfa.exception = None
    monkeypatch.setattr("app.interface.user.InterfaceUserMfa.ModuleMfa", FakeModuleMfa)


def logged_user() -> User:
    user = User("alice@example.com", "pwd", domain="example.com")
    user.mail = "alice@example.com"
    user.authenticated = True
    return user


def test_anonymous_without_mfa_session_refused():
    interface = InterfaceUserMfa(None, DOMAIN, UserAnonymous())
    result, status = interface.get_status()
    assert status == 401
    result, status, headers = interface.begin_enrollment("totp", None, None)
    assert status == 401
    assert headers == {"Cache-Control": "no-store"}
    assert interface.confirm_enrollment("123456", None)[1] == 401
    assert interface.disable("123456", None)[1] == 401


def test_verify_stage_session_cannot_enroll():
    interface = InterfaceUserMfa(None, DOMAIN, UserAnonymous(), FakeMfaSession(cs.MFA_STAGE_VERIFY))
    assert interface.begin_enrollment(None, None, None)[1] == 401


def test_status_for_user():
    interface = InterfaceUserMfa(None, DOMAIN, logged_user())
    result, status = interface.get_status()
    assert status == 200
    assert FakeModuleMfa.last.calls == [("get_status", "alice@example.com")]
    assert FakeModuleMfa.last.auth_settings.SOGO_D_LOGIN_MFA_METHOD == ["totp"]


def test_begin_enrollment_no_store():
    interface = InterfaceUserMfa(None, DOMAIN, logged_user())
    result, status, headers = interface.begin_enrollment("totp", "111111", "1.2.3.4")
    assert status == 200
    assert result["data"]["otpauth_uri"] == "otpauth://totp/x"
    assert headers == {"Cache-Control": "no-store"}
    assert FakeModuleMfa.last.calls == [("begin", "alice@example.com", "totp", "111111", "1.2.3.4")]


def test_begin_enrollment_error_keeps_no_store():
    FakeModuleMfa.exception = RequestException("x", err.ERROR_MFA_PROVIDER_REQUIRED)
    interface = InterfaceUserMfa(None, DOMAIN, logged_user())
    result, status, headers = interface.begin_enrollment(None, None, None)
    assert status == 400
    assert result["error_code"] == err.ERROR_MFA_PROVIDER_REQUIRED.c
    assert headers == {"Cache-Control": "no-store"}


def test_confirm_from_preferences_returns_status():
    interface = InterfaceUserMfa(None, DOMAIN, logged_user())
    result, status = interface.confirm_enrollment("123456", None)
    assert status == 200
    assert result["data"]["method"] == {"provider": "totp"}
    assert [c[0] for c in FakeModuleMfa.last.calls] == ["confirm"]


def test_confirm_from_forced_enrollment_returns_user_voucher():
    session = FakeMfaSession(cs.MFA_STAGE_ENROLL)
    interface = InterfaceUserMfa(None, DOMAIN, UserAnonymous(), session)
    result, status = interface.confirm_enrollment("123456", "1.2.3.4")
    assert status == 200
    assert result["data"] == {"jwt_token": "user-voucher"}
    assert FakeModuleMfa.last.calls == [("confirm", "bob@example.com", "123456", "1.2.3.4", session), ("finish", session)]


def test_confirm_wrong_code_no_session_issued():
    FakeModuleMfa.exception = RequestException("x", err.ERROR_MFA_CODE_INVALID)
    session = FakeMfaSession(cs.MFA_STAGE_ENROLL)
    interface = InterfaceUserMfa(None, DOMAIN, UserAnonymous(), session)
    result, status = interface.confirm_enrollment("000000", None)
    assert status == 401
    assert [c[0] for c in FakeModuleMfa.last.calls] == ["confirm"]


def test_disable_enforced():
    FakeModuleMfa.exception = RequestException("x", err.ERROR_MFA_ENFORCED)
    interface = InterfaceUserMfa(None, DOMAIN, logged_user())
    result, status = interface.disable("123456", None)
    assert status == 403
    assert result["error_code"] == err.ERROR_MFA_ENFORCED.c


def test_disable_success_returns_status():
    interface = InterfaceUserMfa(None, DOMAIN, logged_user())
    result, status = interface.disable("123456", "1.2.3.4")
    assert status == 200
    assert [c[0] for c in FakeModuleMfa.last.calls] == ["disable", "get_status"]
