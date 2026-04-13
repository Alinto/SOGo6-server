"""
Tests unitaires pour ModuleAdminUser (Module layer).
Ces tests utilisent un fake cache (ClientRedis) pour tester la logique métier du module.
"""

import pytest

from app.module.admin.ModuleAdminUser import ModuleAdminUser
from app.utils.exceptions import RequestException
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


def _make_collection_param(page=1, page_size=20, sort_by=None, sort_order=None, fields=None, fields_action=None):
    """Helper to build a CollectionPaginateArgs for tests."""
    return CollectionPaginateArgs(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        fields=fields,
        fields_action=fields_action,
    )


class FakeClientRedis:
    """Fake ClientRedis for testing ModuleAdminUser."""

    def __init__(self):
        # Configurable results
        self.zset_paginate_result = (0, [])
        self.revoke_by_uid_result = 0
        self.revoke_by_key_result = 0
        self.revoke_by_activity_result = 0

        # Track method calls
        self.zset_paginate_calls = []
        self.revoke_by_uid_calls = []
        self.revoke_by_key_calls = []
        self.revoke_by_activity_calls = []

    def zset_paginate_hashes(self, first=0, last=0, sort_by=None, sort_order="desc", include_fields=None):
        self.zset_paginate_calls.append({
            'first': first,
            'last': last,
            'sort_by': sort_by,
            'sort_order': sort_order,
            'include_fields': include_fields,
        })
        if isinstance(self.zset_paginate_result, Exception):
            raise self.zset_paginate_result
        return self.zset_paginate_result

    def revoke_user_sessions_by_uid(self, uids):
        self.revoke_by_uid_calls.append(uids)
        if isinstance(self.revoke_by_uid_result, Exception):
            raise self.revoke_by_uid_result
        return self.revoke_by_uid_result

    def revoke_user_sessions_by_key(self, redis_keys):
        self.revoke_by_key_calls.append(redis_keys)
        if isinstance(self.revoke_by_key_result, Exception):
            raise self.revoke_by_key_result
        return self.revoke_by_key_result

    def revoke_user_sessions_by_activity(self, timestamp):
        self.revoke_by_activity_calls.append(timestamp)
        if isinstance(self.revoke_by_activity_result, Exception):
            raise self.revoke_by_activity_result
        return self.revoke_by_activity_result


def _make_module(monkeypatch, fake_cache=None):
    """Create a ModuleAdminUser with a patched sogo_cache."""
    if fake_cache is None:
        fake_cache = FakeClientRedis()
    monkeypatch.setattr("app.module.admin.ModuleAdminUser.sogo_cache", lambda: fake_cache)
    module = ModuleAdminUser()
    return module, fake_cache


# ========== Tests for initialization ==========

def test_module_init_success():
    """Test ModuleAdminUser can be instantiated without arguments."""
    module = ModuleAdminUser()
    assert isinstance(module, ModuleAdminUser)


# ========== Tests for get_active_users ==========

def test_get_active_users_empty(monkeypatch):
    """Test get_active_users returns empty list when no active sessions."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (0, [])

    total, users = module.get_active_users(_make_collection_param())

    assert total == 0
    assert users == []
    assert len(fake_cache.zset_paginate_calls) == 1


def test_get_active_users_with_results(monkeypatch):
    """Test get_active_users returns active user list."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (2, [
        {'uid': 'user1', 'login': 'user1@example.com'},
        {'uid': 'user2', 'login': 'user2@example.com'},
    ])

    total, users = module.get_active_users(_make_collection_param())

    assert total == 2
    assert len(users) == 2
    assert users[0]['uid'] == 'user1'
    assert users[1]['uid'] == 'user2'


def test_get_active_users_pagination(monkeypatch):
    """Test get_active_users passes pagination parameters to cache."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (50, [{'uid': 'user10'}])

    # page=2, page_size=10 => first_item=10, last_item=19
    module.get_active_users(_make_collection_param(page=2, page_size=10))

    assert len(fake_cache.zset_paginate_calls) == 1
    call = fake_cache.zset_paginate_calls[0]
    assert call['first'] == 10
    assert call['last'] == 19


def test_get_active_users_sort_by_field(monkeypatch):
    """Test get_active_users passes sort_by and sort_order to cache."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (1, [{'uid': 'user1', 'login': 'user1@example.com'}])

    module.get_active_users(_make_collection_param(sort_by='login', sort_order='asc'))

    call = fake_cache.zset_paginate_calls[0]
    assert call['sort_by'] == 'login'
    assert call['sort_order'] == 'asc'


def test_get_active_users_include_fields(monkeypatch):
    """Test get_active_users passes fields to cache via CollectionPaginateArgs."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (1, [{'uid': 'user1'}])

    module.get_active_users(_make_collection_param(fields='uid,login'))

    assert len(fake_cache.zset_paginate_calls) == 1


def test_get_active_users_cache_error(monkeypatch):
    """Test get_active_users propagates exception from cache."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = Exception("Redis unavailable")

    with pytest.raises(Exception, match="Redis unavailable"):
        module.get_active_users(_make_collection_param())


def test_get_active_users_default_sort_order(monkeypatch):
    """Test get_active_users uses None sort order by default when not specified."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (0, [])

    module.get_active_users(_make_collection_param())

    call = fake_cache.zset_paginate_calls[0]
    assert call['sort_order'] is None


def test_get_active_users_returns_tuple(monkeypatch):
    """Test get_active_users returns a tuple (total_count, list)."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.zset_paginate_result = (3, [{'uid': 'u1'}, {'uid': 'u2'}, {'uid': 'u3'}])

    result = module.get_active_users(_make_collection_param())

    assert isinstance(result, tuple)
    assert len(result) == 2
    total, users = result
    assert isinstance(total, int)
    assert isinstance(users, list)


# ========== Tests for revoke_users (by uid) ==========

def test_revoke_users_by_uid_success(monkeypatch):
    """Test revoking sessions by UID list."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_uid_result = 2

    result = module.revoke_users(uids=['user1', 'user2'])

    assert result == 2
    assert len(fake_cache.revoke_by_uid_calls) == 1
    assert fake_cache.revoke_by_uid_calls[0] == ['user1', 'user2']


def test_revoke_users_by_uid_single(monkeypatch):
    """Test revoking a single session by UID."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_uid_result = 1

    result = module.revoke_users(uids=['user1'])

    assert result == 1
    assert fake_cache.revoke_by_uid_calls[0] == ['user1']


def test_revoke_users_by_uid_zero_revoked(monkeypatch):
    """Test revoking sessions by UID when none match."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_uid_result = 0

    result = module.revoke_users(uids=['nonexistent'])

    assert result == 0


def test_revoke_users_by_uid_cache_error(monkeypatch):
    """Test revoke_users by uid wraps cache exception in RequestException."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_uid_result = Exception("Redis connection lost")

    with pytest.raises(RequestException, match="Redis connection lost"):
        module.revoke_users(uids=['user1'])


def test_revoke_users_by_uid_does_not_call_key_revoke(monkeypatch):
    """Test that providing uids does not call revoke_by_key."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_uid_result = 1

    module.revoke_users(uids=['user1'])

    assert len(fake_cache.revoke_by_key_calls) == 0


# ========== Tests for revoke_users (by redis_key) ==========

def test_revoke_users_by_redis_key_success(monkeypatch):
    """Test revoking sessions by Redis key list."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_key_result = 3

    result = module.revoke_users(redis_keys=['key:1', 'key:2', 'key:3'])

    assert result == 3
    assert len(fake_cache.revoke_by_key_calls) == 1
    assert fake_cache.revoke_by_key_calls[0] == ['key:1', 'key:2', 'key:3']


def test_revoke_users_by_redis_key_single(monkeypatch):
    """Test revoking a single session by Redis key."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_key_result = 1

    result = module.revoke_users(redis_keys=['key:abc'])

    assert result == 1


def test_revoke_users_by_redis_key_cache_error(monkeypatch):
    """Test revoke_users by redis_key wraps cache exception in RequestException."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_key_result = Exception("Redis write failed")

    with pytest.raises(RequestException, match="Redis write failed"):
        module.revoke_users(redis_keys=['key:1'])


def test_revoke_users_by_redis_key_does_not_call_uid_revoke(monkeypatch):
    """Test that providing redis_keys does not call revoke_by_uid."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_key_result = 1

    module.revoke_users(redis_keys=['key:1'])

    assert len(fake_cache.revoke_by_uid_calls) == 0


# ========== Tests for revoke_users (invalid parameters) ==========

def test_revoke_users_no_params_raises(monkeypatch):
    """Test revoke_users raises RequestException when no parameters provided."""
    module, fake_cache = _make_module(monkeypatch)

    with pytest.raises(RequestException):
        module.revoke_users()


def test_revoke_users_no_params_error_code(monkeypatch):
    """Test revoke_users raises RequestException with correct error code when no parameters."""
    module, fake_cache = _make_module(monkeypatch)

    with pytest.raises(RequestException) as exc_info:
        module.revoke_users()

    assert exc_info.value.error == err.ERROR_REVOKE_BODY_INVALID


def test_revoke_users_both_params_uses_uid(monkeypatch):
    """Test revoke_users uses uid when both uids and redis_keys are provided (uid takes priority)."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_uid_result = 1

    result = module.revoke_users(uids=['user1'], redis_keys=['key:1'])

    # uids is checked first, so uid revocation should be called
    assert len(fake_cache.revoke_by_uid_calls) == 1
    assert len(fake_cache.revoke_by_key_calls) == 0


# ========== Tests for revoke_inactive_users ==========

def test_revoke_inactive_users_success(monkeypatch):
    """Test revoking inactive sessions by timestamp."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_activity_result = 5

    result = module.revoke_inactive_users(timestamp=1700000000)

    assert result == 5
    assert len(fake_cache.revoke_by_activity_calls) == 1
    assert fake_cache.revoke_by_activity_calls[0] == 1700000000


def test_revoke_inactive_users_none_revoked(monkeypatch):
    """Test revoking inactive sessions when none are older than timestamp."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_activity_result = 0

    result = module.revoke_inactive_users(timestamp=0)

    assert result == 0


def test_revoke_inactive_users_large_count(monkeypatch):
    """Test revoking a large number of inactive sessions."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_activity_result = 9999

    result = module.revoke_inactive_users(timestamp=9999999999)

    assert result == 9999


def test_revoke_inactive_users_passes_correct_timestamp(monkeypatch):
    """Test revoke_inactive_users passes the exact timestamp to the cache."""
    module, fake_cache = _make_module(monkeypatch)
    fake_cache.revoke_by_activity_result = 2

    ts = 1711747200
    module.revoke_inactive_users(timestamp=ts)

    assert fake_cache.revoke_by_activity_calls[0] == ts
