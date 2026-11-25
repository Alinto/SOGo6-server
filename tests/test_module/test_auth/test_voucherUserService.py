"""
Unit tests for the user session of VoucherUserService used by the SSO refresh. Redis is mocked.
"""
import pytest

from app.auth.User import User
from app.auth.service import VoucherUserService as vus
from app.auth.service.VoucherUserService import VoucherUserService
from app.utils import constants as cs
from app.utils.exceptions import RequestException


class FakeProcessSettings:
    SOGO_P_VOUCHER_SECRET = "0123456789abcdef0123456789abcdef"


class FakeHashCache:
    """Fake ClientRedis for hashes"""
    def __init__(self):
        self.data: dict = {}

    def hashget(self, key):
        return self.data.get(key)

    def hashset(self, key, data, ttl):
        self.data.setdefault(key, {}).update(data)
        return True

    def close(self):
        pass


@pytest.fixture
def cache(monkeypatch):
    fake_cache = FakeHashCache()
    monkeypatch.setattr(vus, "sogo_cache", lambda: fake_cache)
    return fake_cache


def get_user(session_id="sid", session_key="k" * 32):
    user = User("user@example.com", "token", domain="example.com")
    user.auth_kind = "openid"
    user.refresh_token = "refresh"
    user.token_expires_at = 1234
    user.session_id = session_id
    user.session_key = session_key
    return user


def test_save_and_read_user_session(cache):
    """The refreshed tokens are saved encrypted in the existing session, its other fields are kept"""
    service = VoucherUserService(FakeProcessSettings())
    cache.data["user_session:sid"] = {cs.USER_UID: "user@example.com", cs.SESSION_SENSITIVE: b"old"}
    user = get_user()
    user.password = "new-token"

    assert service.save_user_session(user)

    session = cache.data["user_session:sid"]
    assert session[cs.USER_UID] == "user@example.com"
    assert b"new-token" not in session[cs.SESSION_SENSITIVE]
    data = service.read_user_session("sid", "k" * 32)
    assert (data[cs.USER_PWD], data[cs.USER_REFRESH_TOKEN], data[cs.USER_TOKEN_EXPIRES_AT]) == ("new-token", "refresh", 1234)
    assert User.init_from_user_session(data).refresh_token == "refresh"


def test_save_user_session_expired(cache):
    """An expired or revoked session is not created again"""
    assert not VoucherUserService(FakeProcessSettings()).save_user_session(get_user())
    assert cache.data == {}


def test_save_user_session_no_session(cache):
    """User not read from a voucher"""
    assert not VoucherUserService(FakeProcessSettings()).save_user_session(get_user(session_id=""))


def test_read_user_session_missing(cache):
    assert VoucherUserService(FakeProcessSettings()).read_user_session("sid", "k" * 32) is None


def test_read_user_session_wrong_key(cache):
    service = VoucherUserService(FakeProcessSettings())
    cache.data["user_session:sid"] = {cs.USER_UID: "user@example.com"}
    service.save_user_session(get_user())
    with pytest.raises(RequestException):
        service.read_user_session("sid", "x" * 32)
