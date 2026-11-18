"""
Unit tests for ModuleMfa: decision matrix, enrollment, disable, admin reset,
rate limiting, login challenge, and a dummy third provider.
"""
import pyotp
import pytest

from app.auth.User import User
from app.auth.service import VoucherMfaService as voucher_mfa_module
from app.auth.service.VoucherMfaService import VoucherMfaService
from app.module.auth.mfa import ModuleMfa as module_mfa_module
from app.module.auth.mfa import ProviderTotp as totp_module
from app.module.auth.mfa.MfaCrypto import MfaCrypto
from app.module.auth.mfa.MfaProvider import MfaContext, MfaProvider
from app.module.auth.mfa.ModuleMfa import (ModuleMfa, MFA_ACTION_NONE, MFA_ACTION_VERIFY, MFA_ACTION_ENROLL)
from app.module.auth.mfa.registry import register_provider, unregister_provider, registered_provider_ids
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException

from tests._mfa_fakes import FakeCache, FakeMfaDB, FakeProcess, auth_settings, totp_code

UID = "alice@example.com"
NOW = 1_700_000_015
IP = "203.0.113.7"


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(module_mfa_module, "sogo_cache", lambda: fake)
    monkeypatch.setattr(voucher_mfa_module, "sogo_cache", lambda: fake)
    return fake


@pytest.fixture
def db(monkeypatch):
    fake = FakeMfaDB({UID: None})
    monkeypatch.setattr(module_mfa_module, "get_sogo6_database", lambda process: fake)
    return fake


@pytest.fixture(autouse=True)
def frozen_time(monkeypatch):
    monkeypatch.setattr(totp_module.time, "time", lambda: NOW)


@pytest.fixture
def fake_user_voucher(monkeypatch):
    class FakeVoucherUserService:
        def __init__(self, process):
            pass

        def generate_voucher_from_user(self, user):
            return f"user-voucher-{user.uid}"
    monkeypatch.setattr(module_mfa_module, "VoucherUserService", FakeVoucherUserService)


def make_module(**kwargs) -> ModuleMfa:
    return ModuleMfa(FakeProcess(), auth_settings(**kwargs))


def make_ctx(module: ModuleMfa) -> MfaContext:
    return MfaContext(uid=UID, mail=UID, auth_settings=module.auth_settings)


def make_user() -> User:
    user = User(UID, "s3cret", domain="example.com")
    user.mail = UID
    return user


def store_totp(db, secret=None) -> str:
    """Store an active TOTP method for UID and return its clear secret."""
    secret = secret or pyotp.random_base32(32)
    db.methods[UID] = {"provider": "totp", "secret": MfaCrypto(FakeProcess()).encrypt(secret),
                       "created_at": "2026-11-16T10:02:00Z", "last_used_at": "2026-11-16T10:02:00Z"}
    return secret


# ---------- settings and decision matrix ----------

@pytest.mark.parametrize("kwargs,expected", [
    ({}, ["totp"]),
    ({"enabled": False}, []),
    ({"methods": ()}, []),
    ({"auth_type": "openid"}, []),
    ({"methods": ("totp", "unknown")}, ["totp"]),
])
def test_allowed_methods(cache, db, kwargs, expected):
    assert make_module(**kwargs).allowed_methods() == expected


def test_no_auth_settings_means_no_mfa(cache, db):
    module = ModuleMfa(FakeProcess(), None)
    assert module.allowed_methods() == []
    assert module.is_enforced() is False


@pytest.mark.parametrize("kwargs,has_method,expected_action", [
    ({"enabled": False}, True, MFA_ACTION_NONE),
    ({}, False, MFA_ACTION_NONE),
    ({}, True, MFA_ACTION_VERIFY),
    ({"force": True}, False, MFA_ACTION_ENROLL),
    ({"force": True}, True, MFA_ACTION_VERIFY),
])
def test_resolve_matrix(cache, db, kwargs, has_method, expected_action):
    if has_method:
        store_totp(db)
    decision = make_module(**kwargs).resolve(UID)
    assert decision.action == expected_action


def test_method_no_longer_allowed_counts_as_none(cache, db):
    store_totp(db)
    #Only "dummy" allowed now: totp is ignored
    register_provider(DummyProvider)
    try:
        assert make_module(methods=("dummy",)).resolve(UID).action == MFA_ACTION_NONE
        decision = make_module(methods=("dummy",), force=True).resolve(UID)
        assert decision.action == MFA_ACTION_ENROLL
        assert decision.allowed_methods == ["dummy"]
    finally:
        unregister_provider("dummy")


def test_get_method_unknown_user(cache, db):
    with pytest.raises(RequestException) as exc:
        make_module().get_method("nobody@example.com")
    assert exc.value.error == err.ERROR_USER_PROFILE_NOT_FOUND


def test_get_method_text_column(cache, db):
    """On MariaDB the column is text: the json is decoded."""
    db.methods[UID] = '{"provider": "totp", "secret": "x"}'
    assert make_module().get_method(UID) == {"provider": "totp", "secret": "x"}


def test_status_never_returns_secret(cache, db):
    store_totp(db)
    status = make_module(force=True).get_status(UID)
    assert status == {
        "enabled": True,
        "enforced": True,
        "allowed_methods": ["totp"],
        "method": {"provider": "totp", "created_at": "2026-11-16T10:02:00Z", "last_used_at": "2026-11-16T10:02:00Z"},
    }


# ---------- enrollment ----------

def test_begin_enrollment_disabled(cache, db):
    module = make_module(enabled=False)
    with pytest.raises(RequestException) as exc:
        module.begin_enrollment(make_ctx(module))
    assert exc.value.error == err.ERROR_MFA_DISABLED


def test_begin_enrollment_not_allowed(cache, db):
    module = make_module()
    with pytest.raises(RequestException) as exc:
        module.begin_enrollment(make_ctx(module), "external_otp")
    assert exc.value.error == err.ERROR_MFA_METHOD_NOT_ALLOWED


def test_begin_enrollment_provider_required_when_several(cache, db):
    register_provider(DummyProvider)
    try:
        module = make_module(methods=("totp", "dummy"))
        with pytest.raises(RequestException) as exc:
            module.begin_enrollment(make_ctx(module))
        assert exc.value.error == err.ERROR_MFA_PROVIDER_REQUIRED
        assert module.begin_enrollment(make_ctx(module), "dummy") == {"provider": "dummy"}
    finally:
        unregister_provider("dummy")


def test_begin_enrollment_stores_pending_only(cache, db):
    module = make_module()
    public = module.begin_enrollment(make_ctx(module), ip=IP)
    assert set(public) == {"provider", "otpauth_uri", "secret"}
    pending = cache.get(f"{cs.MFA_ENROLL_PREFIX}{UID}", dict)
    assert pending["provider"] == "totp"
    assert pending["secret"] != public["secret"]
    assert cache.ttls[f"{cs.MFA_ENROLL_PREFIX}{UID}"] == cs.TTL_MFA_ENROLL
    #Nothing written to the profile yet
    assert db.methods[UID] is None


def test_replace_method_requires_current_code(cache, db):
    secret = store_totp(db)
    module = make_module()
    with pytest.raises(RequestException) as exc:
        module.begin_enrollment(make_ctx(module))
    assert exc.value.error == err.ERROR_MFA_CODE_REQUIRED

    with pytest.raises(RequestException) as exc:
        module.begin_enrollment(make_ctx(module), current_code=totp_code(secret, NOW - 3600))
    assert exc.value.error == err.ERROR_MFA_CODE_INVALID

    public = module.begin_enrollment(make_ctx(module), current_code=totp_code(secret, NOW))
    assert "otpauth_uri" in public
    #The current method stays in use until the new one is confirmed
    assert db.methods[UID]["secret"] != cache.get(f"{cs.MFA_ENROLL_PREFIX}{UID}", dict)["secret"]


def test_confirm_enrollment_no_pending(cache, db):
    module = make_module()
    with pytest.raises(RequestException) as exc:
        module.confirm_enrollment(make_ctx(module), "123456")
    assert exc.value.error == err.ERROR_MFA_NO_PENDING_ENROLLMENT


def test_confirm_enrollment_wrong_code(cache, db):
    module = make_module()
    public = module.begin_enrollment(make_ctx(module))
    with pytest.raises(RequestException) as exc:
        module.confirm_enrollment(make_ctx(module), totp_code(public["secret"], NOW - 3600), IP)
    assert exc.value.error == err.ERROR_MFA_CODE_INVALID
    assert db.methods[UID] is None
    assert cache.store[f"{cs.MFA_RL_USER_PREFIX}{UID}"] == "1"
    assert cache.store[f"{cs.MFA_RL_IP_PREFIX}{IP}"] == "1"


def test_confirm_enrollment_saves_method(cache, db):
    module = make_module()
    public = module.begin_enrollment(make_ctx(module))
    pending_secret = cache.get(f"{cs.MFA_ENROLL_PREFIX}{UID}", dict)["secret"]

    status = module.confirm_enrollment(make_ctx(module), totp_code(public["secret"], NOW))

    stored = db.methods[UID]
    assert stored["provider"] == "totp"
    assert stored["secret"] == pending_secret
    assert stored["created_at"] and stored["last_used_at"]
    assert f"{cs.MFA_ENROLL_PREFIX}{UID}" not in cache.store
    assert status["method"]["provider"] == "totp"
    assert "secret" not in status["method"]


# ---------- disable / admin reset ----------

def test_disable_enforced(cache, db):
    store_totp(db)
    module = make_module(force=True)
    with pytest.raises(RequestException) as exc:
        module.disable(make_ctx(module), "123456")
    assert exc.value.error == err.ERROR_MFA_ENFORCED
    assert exc.value.error.h == 403


def test_disable_without_method(cache, db):
    module = make_module()
    with pytest.raises(RequestException) as exc:
        module.disable(make_ctx(module), "123456")
    assert exc.value.error == err.ERROR_MFA_NOT_SET


def test_disable_wrong_then_good_code(cache, db):
    secret = store_totp(db)
    module = make_module()
    with pytest.raises(RequestException) as exc:
        module.disable(make_ctx(module), totp_code(secret, NOW - 3600))
    assert exc.value.error == err.ERROR_MFA_CODE_INVALID
    assert db.methods[UID] is not None

    module.disable(make_ctx(module), totp_code(secret, NOW))
    assert db.methods[UID] is None


def test_admin_reset(cache, db):
    store_totp(db)
    cache.set(f"{cs.MFA_ENROLL_PREFIX}{UID}", {"provider": "totp"}, 600)
    module = ModuleMfa(FakeProcess(), None)
    assert module.admin_reset(UID) is True
    assert db.methods[UID] is None
    assert f"{cs.MFA_ENROLL_PREFIX}{UID}" not in cache.store
    assert module.admin_reset(UID) is False


def test_admin_reset_unknown_user(cache, db):
    with pytest.raises(RequestException) as exc:
        ModuleMfa(FakeProcess(), None).admin_reset("nobody@example.com")
    assert exc.value.error == err.ERROR_USER_PROFILE_NOT_FOUND


# ---------- rate limiting ----------

def test_rate_limit_per_user(cache, db):
    secret = store_totp(db)
    module = make_module()
    for _ in range(cs.MFA_RL_USER_MAX):
        with pytest.raises(RequestException) as exc:
            module.disable(make_ctx(module), totp_code(secret, NOW - 3600))
        assert exc.value.error == err.ERROR_MFA_CODE_INVALID
    #Even the good code is refused now
    with pytest.raises(RequestException) as exc:
        module.disable(make_ctx(module), totp_code(secret, NOW))
    assert exc.value.error == err.ERROR_MFA_TOO_MANY_ATTEMPTS
    assert cache.ttls[f"{cs.MFA_RL_USER_PREFIX}{UID}"] == cs.MFA_RL_WINDOW


def test_rate_limit_per_ip(cache, db):
    secret = store_totp(db)
    cache.store[f"{cs.MFA_RL_IP_PREFIX}{IP}"] = str(cs.MFA_RL_IP_MAX)
    module = make_module()
    with pytest.raises(RequestException) as exc:
        module.disable(make_ctx(module), totp_code(secret, NOW), IP)
    assert exc.value.error == err.ERROR_MFA_TOO_MANY_ATTEMPTS
    #Another IP is not blocked
    module.disable(make_ctx(module), totp_code(secret, NOW), "198.51.100.1")


# ---------- login ----------

def test_start_login_without_mfa(cache, db):
    assert make_module().start_login(make_user()) is None


def test_start_login_verify(cache, db):
    store_totp(db)
    ret = make_module().start_login(make_user(), IP)
    assert ret["mfa_required"] is True
    assert ret["provider"] == "totp"
    session = VoucherMfaService(FakeProcess()).read_session(ret["mfa_token"])
    assert session.stage == cs.MFA_STAGE_VERIFY
    assert session.provider == "totp"


def test_start_login_enroll(cache, db):
    ret = make_module(force=True).start_login(make_user())
    assert ret["enrollment_required"] is True
    assert ret["allowed_methods"] == ["totp"]
    session = VoucherMfaService(FakeProcess()).read_session(ret["mfa_token"])
    assert session.stage == cs.MFA_STAGE_ENROLL


def _verify_session(db):
    secret = store_totp(db)
    module = make_module()
    token = module.start_login(make_user())["mfa_token"]
    return module, secret, VoucherMfaService(FakeProcess()).read_session(token)


def test_verify_login_success(cache, db):
    module, secret, session = _verify_session(db)
    previous_last_used = db.methods[UID]["last_used_at"]

    user = module.verify_login(session, totp_code(secret, NOW), IP)

    assert user.uid == UID
    assert user.password == "s3cret"
    assert session.redis_key not in cache.hashes
    assert db.methods[UID]["last_used_at"] != previous_last_used


def test_verify_login_wrong_code_then_killed(cache, db):
    module, secret, session = _verify_session(db)
    wrong = totp_code(secret, NOW - 3600)
    for _ in range(cs.MFA_MAX_ATTEMPTS - 1):
        with pytest.raises(RequestException) as exc:
            module.verify_login(session, wrong)
        assert exc.value.error == err.ERROR_MFA_CODE_INVALID
    with pytest.raises(RequestException) as exc:
        module.verify_login(session, wrong)
    assert exc.value.error == err.ERROR_MFA_TOO_MANY_ATTEMPTS
    #The MFA session is gone: the user must log in again
    assert session.redis_key not in cache.hashes


def test_verify_login_method_reset_meanwhile(cache, db):
    module, secret, session = _verify_session(db)
    db.methods[UID] = None
    with pytest.raises(RequestException) as exc:
        module.verify_login(session, totp_code(secret, NOW))
    assert exc.value.error == err.ERROR_MFA_SESSION_INVALID
    assert session.redis_key not in cache.hashes


def test_verify_login_refuses_enroll_session(cache, db):
    module = make_module(force=True)
    token = module.start_login(make_user())["mfa_token"]
    session = VoucherMfaService(FakeProcess()).read_session(token)
    with pytest.raises(RequestException) as exc:
        module.verify_login(session, "123456")
    assert exc.value.error == err.ERROR_MFA_SESSION_INVALID


def test_forced_enrollment_then_session(cache, db, fake_user_voucher):
    module = make_module(force=True)
    token = module.start_login(make_user())["mfa_token"]
    session = VoucherMfaService(FakeProcess()).read_session(token)
    ctx = MfaContext(uid=session.uid, mail=session.mail, auth_settings=module.auth_settings)

    public = module.begin_enrollment(ctx)
    module.confirm_enrollment(ctx, totp_code(public["secret"], NOW), mfa_session=session)
    ret = module.finish_enrollment_login(session)

    assert ret == {"jwt_token": f"user-voucher-{UID}"}
    assert db.methods[UID]["provider"] == "totp"
    assert session.redis_key not in cache.hashes


def test_forced_enrollment_wrong_codes_kill_session(cache, db):
    module = make_module(force=True)
    token = module.start_login(make_user())["mfa_token"]
    session = VoucherMfaService(FakeProcess()).read_session(token)
    ctx = MfaContext(uid=session.uid, mail=session.mail, auth_settings=module.auth_settings)
    public = module.begin_enrollment(ctx)
    wrong = totp_code(public["secret"], NOW - 3600)
    for _ in range(cs.MFA_MAX_ATTEMPTS - 1):
        with pytest.raises(RequestException):
            module.confirm_enrollment(ctx, wrong, mfa_session=session)
    with pytest.raises(RequestException) as exc:
        module.confirm_enrollment(ctx, wrong, mfa_session=session)
    assert exc.value.error == err.ERROR_MFA_TOO_MANY_ATTEMPTS
    assert session.redis_key not in cache.hashes


# ---------- third provider: no change to the login flow ----------

class DummyProvider(MfaProvider):
    """Accepts the code 4242, records its calls."""
    id = "dummy"
    calls: list = []

    def begin_enrollment(self):
        return {"provider": self.id}, {"provider": self.id}

    def confirm_enrollment(self, pending, code):
        return {"provider": self.id} if code == "4242" else None

    def start_challenge(self, method):
        DummyProvider.calls.append("start_challenge")
        return {"sent": True}

    def verify(self, method, challenge, code):
        DummyProvider.calls.append(("verify", challenge))
        return code == "4242"


def test_dummy_provider_full_flow(cache, db, fake_user_voucher):
    register_provider(DummyProvider)
    DummyProvider.calls = []
    try:
        assert "dummy" in registered_provider_ids()
        module = make_module(methods=("dummy",))
        ctx = make_ctx(module)
        module.begin_enrollment(ctx)
        module.confirm_enrollment(ctx, "4242")

        ret = module.start_login(make_user())
        assert ret["provider"] == "dummy"
        session = VoucherMfaService(FakeProcess()).read_session(ret["mfa_token"])
        user = module.verify_login(session, "4242")

        assert user.uid == UID
        assert DummyProvider.calls == ["start_challenge", ("verify", {"sent": True})]
    finally:
        unregister_provider("dummy")
    assert "dummy" not in registered_provider_ids()


def test_external_otp_not_registered_yet():
    assert "external_otp" not in registered_provider_ids()


def test_register_provider_without_id():
    class NoId(DummyProvider):
        id = ""
    with pytest.raises(ValueError):
        register_provider(NoId)
