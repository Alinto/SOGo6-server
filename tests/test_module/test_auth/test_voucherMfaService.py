"""
Unit tests for VoucherMfaService and the MFA access table.
"""
import jwt
import pytest

from app.auth.User import User, UserAnonymous
from app.auth.mfa_access import is_endpoint_allowed_for_mfa_stage, MFA_ENDPOINT_VERIFY, MFA_ENDPOINT_BEGIN, MFA_ENDPOINT_CONFIRM
from app.auth.service import VoucherMfaService as voucher_mfa_module
from app.auth.service import VoucherUserService as voucher_user_module
from app.auth.service.VoucherMfaService import VoucherMfaService
from app.auth.service.VoucherUserService import VoucherUserService
from app.auth.voucher.JWTVoucher import JWTVoucher
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException

from tests._mfa_fakes import FakeCache, FakeProcess, VOUCHER_SECRET


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(voucher_mfa_module, "sogo_cache", lambda: fake)
    monkeypatch.setattr(voucher_user_module, "sogo_cache", lambda: fake)
    return fake


@pytest.fixture
def service():
    return VoucherMfaService(FakeProcess())


def make_user() -> User:
    user = User("alice@example.com", "s3cret", domain="example.com")
    user.mail = "alice@example.com"
    user.source_id = "ldap1"
    return user


def test_create_and_read_verify_session(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp", challenge={"a": 1})

    claims = jwt.decode(token, VOUCHER_SECRET, algorithms=["HS256"])
    assert claims[cs.MFA_KIND_CLAIM] == cs.MFA_KIND
    assert claims[cs.MFA_STAGE_CLAIM] == cs.MFA_STAGE_VERIFY

    session = service.read_session(token)
    assert session is not None
    assert session.uid == "alice@example.com"
    assert session.mail == "alice@example.com"
    assert session.domain == "example.com"
    assert session.stage == cs.MFA_STAGE_VERIFY
    assert session.provider == "totp"
    assert session.challenge == {"a": 1}
    assert cache.ttls[session.redis_key] == cs.TTL_MFA_SESSION_VERIFY


def test_password_is_not_stored_in_clear(cache, service):
    service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    stored = next(iter(cache.hashes.values()))
    assert all("s3cret" not in value for value in stored.values())


def test_enroll_session_ttl_and_allowed_methods(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_ENROLL, allowed_methods=["totp"])
    session = service.read_session(token)
    assert session.stage == cs.MFA_STAGE_ENROLL
    assert session.allowed_methods == ["totp"]
    assert cache.ttls[session.redis_key] == cs.TTL_MFA_SESSION_ENROLL


def test_create_unknown_stage(cache, service):
    from app.utils.exceptions import BugException
    with pytest.raises(BugException):
        service.create(make_user(), "whatever")


def test_is_mfa_voucher(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    user_token = JWTVoucher(VOUCHER_SECRET).create_voucher({cs.USER_UID: "alice@example.com"}, 60)
    assert VoucherMfaService.is_mfa_voucher(token) is True
    assert VoucherMfaService.is_mfa_voucher(user_token) is False
    assert VoucherMfaService.is_mfa_voucher("garbage") is False
    assert VoucherMfaService.is_mfa_voucher(None) is False


def test_read_session_forged_voucher(cache, service):
    """A voucher signed with another secret is refused even if it claims kind=mfa."""
    service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    forged = jwt.encode({cs.USER_UID: "alice@example.com", cs.MFA_KIND_CLAIM: cs.MFA_KIND,
                         cs.MFA_STAGE_CLAIM: cs.MFA_STAGE_VERIFY, cs.SESSION_KEY: "x"}, "b" * 32, algorithm="HS256")
    assert service.read_session(forged) is None


def test_read_session_expired_in_cache(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    cache.hashes.clear()
    assert service.read_session(token) is None


def test_read_session_stage_mismatch(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_ENROLL)
    key = next(iter(cache.hashes))
    cache.hashes[key]["stage"] = cs.MFA_STAGE_VERIFY
    assert service.read_session(token) is None


def test_read_session_user_voucher_refused(cache, service):
    user_token = JWTVoucher(VOUCHER_SECRET).create_voucher({cs.USER_UID: "alice@example.com"}, 60)
    assert service.read_session(user_token) is None


def test_consume_returns_user_once(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    session = service.read_session(token)

    user = service.consume(session)
    assert user.uid == "alice@example.com"
    assert user.password == "s3cret"
    assert user.mail == "alice@example.com"
    assert user.source_id == "ldap1"
    assert session.redis_key not in cache.hashes

    with pytest.raises(RequestException) as exc:
        service.consume(session)
    assert exc.value.error == err.ERROR_MFA_SESSION_INVALID


def test_register_failure_and_delete(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    session = service.read_session(token)
    assert service.register_failure(session) == 1
    assert service.register_failure(session) == 2
    service.delete(session)
    assert service.read_session(token) is None


def test_mfa_voucher_is_never_a_user_session(cache, service):
    token = service.create(make_user(), cs.MFA_STAGE_VERIFY, provider="totp")
    user = VoucherUserService(FakeProcess()).generate_user_from_voucher(token)
    assert isinstance(user, UserAnonymous)


@pytest.mark.parametrize("stage,endpoint,method,expected", [
    (cs.MFA_STAGE_VERIFY, MFA_ENDPOINT_VERIFY, "POST", True),
    (cs.MFA_STAGE_VERIFY, MFA_ENDPOINT_BEGIN, "POST", False),
    (cs.MFA_STAGE_VERIFY, MFA_ENDPOINT_CONFIRM, "POST", False),
    (cs.MFA_STAGE_ENROLL, MFA_ENDPOINT_BEGIN, "POST", True),
    (cs.MFA_STAGE_ENROLL, MFA_ENDPOINT_CONFIRM, "post", True),
    (cs.MFA_STAGE_ENROLL, MFA_ENDPOINT_BEGIN, "GET", False),
    (cs.MFA_STAGE_ENROLL, MFA_ENDPOINT_BEGIN, "DELETE", False),
    (cs.MFA_STAGE_ENROLL, MFA_ENDPOINT_VERIFY, "POST", False),
    (cs.MFA_STAGE_ENROLL, "user#Preferences.v1_Preferences.Preferences.ApiUserPreferences", "GET", False),
    (cs.MFA_STAGE_VERIFY, "user#Mail Account.v1_Mail Account.Mail Account.ApiMailMailbox", "GET", False),
    ("unknown", MFA_ENDPOINT_VERIFY, "POST", False),
    (cs.MFA_STAGE_VERIFY, None, "POST", False),
])
def test_mfa_stage_endpoints(stage, endpoint, method, expected):
    assert is_endpoint_allowed_for_mfa_stage(stage, endpoint, method) is expected
