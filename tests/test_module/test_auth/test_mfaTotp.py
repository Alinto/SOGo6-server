"""
Unit tests for ProviderTotp: RFC 6238 vectors, +-1 step window, replay protection.
"""
from urllib.parse import urlparse, parse_qs

import pyotp
import pytest

from app.module.auth.mfa import ProviderTotp as totp_module
from app.module.auth.mfa.MfaCrypto import MfaCrypto
from app.module.auth.mfa.MfaProvider import MfaContext
from app.module.auth.mfa.ProviderTotp import ProviderTotp, TOTP_PERIOD
from app.utils.exceptions import BugException
from app.utils import errors as err

from tests._mfa_fakes import FakeCache, FakeProcess, auth_settings, totp_code

#RFC 6238 appendix B, SHA-1 seed "12345678901234567890"
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
RFC_VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


@pytest.fixture
def cache():
    return FakeCache()


@pytest.fixture
def crypto():
    return MfaCrypto(FakeProcess())


@pytest.fixture
def provider(cache, crypto):
    ctx = MfaContext(uid="alice@example.com", mail="alice@example.com", auth_settings=auth_settings(issuer="My SOGo"))
    return ProviderTotp(ctx, cache, crypto)


def freeze_time(monkeypatch, at: float):
    monkeypatch.setattr(totp_module.time, "time", lambda: at)


@pytest.mark.parametrize("at,expected", RFC_VECTORS)
def test_rfc6238_vectors_8_digits(at, expected):
    """pyotp with SHA-1 gives the RFC 6238 vectors."""
    assert pyotp.TOTP(RFC_SECRET, digits=8).at(at) == expected


@pytest.mark.parametrize("at,expected", RFC_VECTORS)
def test_verify_rfc6238_vectors_6_digits(monkeypatch, provider, crypto, at, expected):
    """The provider accepts the last 6 digits of the RFC vectors."""
    freeze_time(monkeypatch, at)
    method = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    assert provider.verify(method, {}, expected[-6:]) is True


@pytest.mark.parametrize("offset", [-TOTP_PERIOD, 0, TOTP_PERIOD])
def test_verify_accepts_previous_current_next_step(monkeypatch, provider, crypto, offset):
    now = 1_700_000_015
    freeze_time(monkeypatch, now)
    method = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    assert provider.verify(method, {}, totp_code(RFC_SECRET, now + offset)) is True


@pytest.mark.parametrize("offset", [-2 * TOTP_PERIOD, 2 * TOTP_PERIOD])
def test_verify_refuses_outside_window(monkeypatch, provider, crypto, offset):
    now = 1_700_000_015
    freeze_time(monkeypatch, now)
    method = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    assert provider.verify(method, {}, totp_code(RFC_SECRET, now + offset)) is False


def test_verify_refuses_replay(monkeypatch, provider, crypto):
    now = 1_700_000_015
    freeze_time(monkeypatch, now)
    method = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    code = totp_code(RFC_SECRET, now)
    assert provider.verify(method, {}, code) is True
    assert provider.verify(method, {}, code) is False


def test_replay_marker_ttl_covers_window(monkeypatch, provider, cache, crypto):
    now = 1_700_000_015
    freeze_time(monkeypatch, now)
    method = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    provider.verify(method, {}, totp_code(RFC_SECRET, now))
    assert list(cache.ttls.values()) == [3 * TOTP_PERIOD]


def test_same_step_for_another_secret_is_not_a_replay(monkeypatch, provider, crypto):
    """A code of the current method then a code of the new method at the same step are both accepted."""
    now = 1_700_000_015
    freeze_time(monkeypatch, now)
    other_secret = pyotp.random_base32(32)
    current = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    new = {"provider": "totp", "secret": crypto.encrypt(other_secret)}
    assert provider.verify(current, {}, totp_code(RFC_SECRET, now)) is True
    assert provider.verify(new, {}, totp_code(other_secret, now)) is True


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 456", None, 123456])
def test_verify_refuses_bad_format(monkeypatch, provider, crypto, code):
    freeze_time(monkeypatch, 59)
    method = {"provider": "totp", "secret": crypto.encrypt(RFC_SECRET)}
    assert provider.verify(method, {}, code) is False


def test_verify_unreadable_secret_raises(provider):
    method = {"provider": "totp", "secret": "not-a-fernet-token"}
    with pytest.raises(BugException) as exc:
        provider.verify(method, {}, "123456")
    assert exc.value.error == err.ERROR_MFA_SECRET_UNREADABLE


def test_begin_enrollment_returns_uri_and_encrypted_pending(provider, crypto):
    public, pending = provider.begin_enrollment()

    secret = public["secret"]
    assert len(secret) == 32
    assert public["provider"] == "totp"
    assert pending["provider"] == "totp"
    assert pending["secret"] != secret
    assert crypto.decrypt(pending["secret"]) == secret

    uri = urlparse(public["otpauth_uri"])
    assert uri.scheme == "otpauth"
    assert uri.netloc == "totp"
    assert "alice%40example.com" in uri.path or "alice@example.com" in uri.path
    query = parse_qs(uri.query)
    assert query["secret"] == [secret]
    assert query["issuer"] == ["My SOGo"]


def test_begin_enrollment_generates_a_new_secret_each_time(provider):
    first, _ = provider.begin_enrollment()
    second, _ = provider.begin_enrollment()
    assert first["secret"] != second["secret"]


def test_confirm_enrollment_good_code_then_same_code_refused_at_login(monkeypatch, provider):
    now = 1_700_000_015
    freeze_time(monkeypatch, now)
    public, pending = provider.begin_enrollment()
    code = totp_code(public["secret"], now)

    method = provider.confirm_enrollment(pending, code)
    assert method == {"provider": "totp", "secret": pending["secret"]}
    #The confirmation code can't be reused to log in
    assert provider.verify(method, {}, code) is False


def test_confirm_enrollment_wrong_code(monkeypatch, provider):
    freeze_time(monkeypatch, 1_700_000_015)
    #A code computed for a time far away is always wrong
    public, pending = provider.begin_enrollment()
    assert provider.confirm_enrollment(pending, totp_code(public["secret"], 1_000_000_000)) is None


def test_start_challenge_is_noop(provider):
    assert provider.start_challenge({"provider": "totp"}) == {}


def test_crypto_key_differs_from_session_key(crypto):
    """The MFA key is derived: a token of the session Fernet key can't be read."""
    from base64 import urlsafe_b64encode
    from cryptography.fernet import Fernet
    session_fernet = Fernet(urlsafe_b64encode(FakeProcess.SOGO_P_VOUCHER_SECRET.encode()))
    token = session_fernet.encrypt(b"secret").decode()
    with pytest.raises(BugException):
        crypto.decrypt(token)
