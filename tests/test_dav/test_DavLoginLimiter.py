"""Unit tests for DavLoginLimiter - the cache is a fake."""

from unittest.mock import patch

import pytest

from app.config.settings.DomainSettings import AuthSettingsObj
from app.dav.DavLoginLimiter import DavLoginLimiter
from app.utils import errors as err
from app.utils.exceptions import RequestException

SETTINGS = AuthSettingsObj(
    {"SOGO_D_LOGIN_CHECK_MAX_ATTEMPT": 3, "SOGO_D_LOGIN_CHECK_TIME_SPAN": 60, "SOGO_D_LOGIN_CHECK_BLOCK_TIME": 30}
)


class FakeCache:
    def __init__(self):
        self.keys = {}
        self.hashes = {}
        self.calls = []

    def get(self, key, expected_type):
        self.calls.append(("get", key))
        return self.keys.get(key)

    def hashset(self, key, data, ttl):
        self.calls.append(("hashset", key, ttl))
        self.hashes.setdefault(key, {}).update(data)
        return True

    def hashget(self, key):
        self.calls.append(("hashget", key))
        return dict(self.hashes.get(key, {}))

    def set(self, key, value, ttl):
        self.calls.append(("set", key, ttl))
        self.keys[key] = value
        return True

    def delete(self, *keys):
        self.calls.append(("delete", *keys))
        for key in keys:
            self.hashes.pop(key, None)
        return len(keys)


@pytest.fixture(autouse=True)
def encryption_key():
    with patch("app.dav.DavLoginLimiter.get_encryption_key", return_value=b"k" * 32):
        yield


def _fail(limiter, login, count):
    for attempt in range(count):
        limiter.record_failure(login, f"wrong{attempt}", SETTINGS)


# ========== Tests for the blocked logins ==========


def test_free_login_accepted():
    DavLoginLimiter(FakeCache()).check_not_blocked("alice@example.org", SETTINGS)


def test_blocked_after_distinct_wrong_passwords():
    cache = FakeCache()
    limiter = DavLoginLimiter(cache)
    _fail(limiter, "alice@example.org", SETTINGS.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT - 1)
    limiter.check_not_blocked("alice@example.org", SETTINGS)

    limiter.record_failure("alice@example.org", "last", SETTINGS)
    with pytest.raises(RequestException) as ex:
        limiter.check_not_blocked("alice@example.org", SETTINGS)
    assert ex.value.error is err.ERROR_DAV_LOGIN_BLOCKED
    assert ("set", "dav_login_blocked:alice@example.org", SETTINGS.SOGO_D_LOGIN_CHECK_BLOCK_TIME) in cache.calls
    assert not cache.hashes


def test_same_wrong_password_counted_once():
    limiter = DavLoginLimiter(FakeCache())
    for _ in range(SETTINGS.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT * 2):
        limiter.record_failure("alice@example.org", "old password", SETTINGS)
    limiter.check_not_blocked("alice@example.org", SETTINGS)


def test_login_variants_share_counters():
    limiter = DavLoginLimiter(FakeCache())
    _fail(limiter, "Alice@example.org", SETTINGS.SOGO_D_LOGIN_CHECK_MAX_ATTEMPT - 1)
    limiter.record_failure("alice@example.org", "last", SETTINGS)
    for variant in ("ALICE@example.org", "\u00e1lice@example.org", "a\u0301lice@example.org"):
        with pytest.raises(RequestException):
            limiter.check_not_blocked(variant, SETTINGS)


def test_window_follows_last_failure():
    cache = FakeCache()
    _fail(DavLoginLimiter(cache), "alice@example.org", 2)
    hashsets = [call for call in cache.calls if call[0] == "hashset"]
    assert hashsets == [("hashset", "dav_login_failure:alice@example.org", SETTINGS.SOGO_D_LOGIN_CHECK_TIME_SPAN)] * 2


def test_fingerprint_hides_password():
    cache = FakeCache()
    DavLoginLimiter(cache).record_failure("alice@example.org", "wrong", SETTINGS)
    fingerprint = next(iter(cache.hashes["dav_login_failure:alice@example.org"]))
    assert "wrong" not in fingerprint
    assert len(fingerprint) == 64


def test_blocking_off():
    cache = FakeCache()
    settings = AuthSettingsObj({"SOGO_D_LOGIN_CHECK_MAX_ATTEMPT": 0})
    limiter = DavLoginLimiter(cache)
    limiter.record_failure("alice@example.org", "wrong", settings)
    limiter.check_not_blocked("alice@example.org", settings)
    assert not cache.calls
