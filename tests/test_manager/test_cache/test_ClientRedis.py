"""
Unit tests for ClientRedis (Manager layer).
These tests use mock objects to simulate Redis responses.
"""
from unittest import mock
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from redis import exceptions as rexc

from app.manager.cache.ClientRedis import ClientRedis, SORT_FIELD_TO_ZSET
from app.utils.exceptions import AggravatedException, BugException
from app.utils import constants as cs


# ---------------------------------------------------------------------------
# Fake Redis connection
# ---------------------------------------------------------------------------

class FakePipeline:
    """Minimal fake that mimics a Redis pipeline."""

    def __init__(self, results=None):
        self._commands = []
        self._results = results if results is not None else []

    def hgetall(self, key):
        self._commands.append(("hgetall", key))
        return self

    def hget(self, key, field):
        self._commands.append(("hget", key, field))
        return self

    def delete(self, key):
        self._commands.append(("delete", key))
        return self

    def zrem(self, zset_key, member):
        self._commands.append(("zrem", zset_key, member))
        return self

    def zremrangebyscore(self, zset_key, min_score, max_score):
        self._commands.append(("zremrangebyscore", zset_key, min_score, max_score))
        return self

    def execute(self):
        return self._results


class FakeRedis:
    """Minimal fake that mimics the redis.Redis client."""

    def __init__(self):
        self._store: dict = {}
        self._hashes: dict = {}
        self._zsets: dict = {}

        # Configurable behaviour
        self.ping_should_raise_auth_error = False
        self.ping_should_raise_connection_error = False
        self.set_should_raise_response_error = False
        self.get_return_value = None
        self.pipeline_results: list = []

    # --- basic ---

    def ping(self):
        if self.ping_should_raise_auth_error:
            raise rexc.AuthenticationError("auth error")
        if self.ping_should_raise_connection_error:
            raise rexc.ConnectionError("connection error")
        return True

    def set(self, name, value, ex=None, nx=None):
        if self.set_should_raise_response_error:
            raise rexc.ResponseError("response error")
        if nx and name in self._store:
            return None
        self._store[name] = value
        return True

    def get(self, key):
        return self.get_return_value

    # --- hash ---

    def hset(self, key, mapping=None):
        if key not in self._hashes:
            self._hashes[key] = {}
        if mapping:
            self._hashes[key].update(mapping)
        return len(mapping) if mapping else 0

    def hgetall(self, key):
        return self._hashes.get(key, {})

    def expire(self, key, ttl):
        return True

    # --- sorted sets ---

    def zadd(self, key, mapping):
        if key not in self._zsets:
            self._zsets[key] = {}
        self._zsets[key].update(mapping)
        return 1

    def zrem(self, key, *members):
        removed = 0
        for m in members:
            if key in self._zsets and m in self._zsets[key]:
                del self._zsets[key][m]
                removed += 1
        return removed

    def zcard(self, key):
        return len(self._zsets.get(key, {}))

    def zrange(self, key, start, end, desc=False):
        members = list(self._zsets.get(key, {}).keys())
        if desc:
            members = list(reversed(members))
        if end == -1:
            return members[start:]
        return members[start:end + 1]

    def zrangebyscore(self, key, min, max):
        zset = self._zsets.get(key, {})
        result = []
        for member, score in zset.items():
            try:
                score_val = float(score)
                max_val = float("inf") if max == "+inf" else float(max)
                min_val = float("-inf") if min == "-inf" else float(min)
                if min_val <= score_val <= max_val:
                    result.append(member)
            except (TypeError, ValueError):
                pass
        return result

    def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                removed += 1
            if key in self._hashes:
                del self._hashes[key]
                removed += 1
        return removed

    # --- pipeline ---

    def pipeline(self, transaction=True):
        return FakePipeline(results=self.pipeline_results)


# ---------------------------------------------------------------------------
# Helper: build a ClientRedis with a FakeRedis injected
# ---------------------------------------------------------------------------

def make_client(resp3: bool = False) -> ClientRedis:
    """
    Build a ClientRedis bypassing the real Redis.from_url call.
    resp3=False avoids the CacheConfig import complexity.
    """
    with patch("app.manager.cache.ClientRedis.Redis") as MockRedis:
        MockRedis.from_url.return_value = FakeRedis()
        client = ClientRedis("redis://localhost:6379/0", resp3=resp3)
    # Swap the internal redis attribute with a controllable FakeRedis
    client.redis = FakeRedis()
    return client


# ===========================================================================
# Tests: __init__
# ===========================================================================

class TestClientRedisInit:
    def test_init_resp3_false_sets_cache_false(self):
        with patch("app.manager.cache.ClientRedis.Redis") as MockRedis:
            MockRedis.from_url.return_value = MagicMock()
            client = ClientRedis("redis://localhost:6379/0", resp3=False)
        assert client.cache is False

    def test_init_resp3_true_sets_cache_true(self):
        with patch("app.manager.cache.ClientRedis.Redis") as MockRedis:
            with patch("app.manager.cache.ClientRedis.CacheConfig"):
                MockRedis.from_url.return_value = MagicMock()
                client = ClientRedis("redis://localhost:6379/0", resp3=True)
        assert client.cache is True

    def test_init_creates_redis_instance(self):
        with patch("app.manager.cache.ClientRedis.Redis") as MockRedis:
            MockRedis.from_url.return_value = MagicMock()
            client = ClientRedis("redis://localhost:6379/0", resp3=False)
        assert client.redis is not None


# ===========================================================================
# Tests: ping
# ===========================================================================

class TestPing:
    def test_ping_success(self):
        client = make_client()
        # Should not raise
        client.ping()

    def test_ping_auth_error_raises_aggravated_exception(self):
        client = make_client()
        client.redis.ping_should_raise_auth_error = True
        with pytest.raises(AggravatedException, match="Redis server authentication failed"):
            client.ping()

    def test_ping_connection_error_raises_aggravated_exception(self):
        client = make_client()
        client.redis.ping_should_raise_connection_error = True
        with pytest.raises(AggravatedException, match="Redis server is unavailable"):
            client.ping()


# ===========================================================================
# Tests: set
# ===========================================================================

class TestSet:
    def test_set_string_value_returns_true(self):
        client = make_client()
        result = client.set("key1", "hello", ttl=60)
        assert result is True

    def test_set_dict_value_serializes_to_json(self):
        client = make_client()
        result = client.set("key2", {"a": 1}, ttl=60)
        assert result is True
        # Verify it was stored as JSON string
        assert client.redis._store["key2"] == '{"a": 1}'

    def test_set_list_value_serializes_to_json(self):
        client = make_client()
        result = client.set("key3", [1, 2, 3], ttl=60)
        assert result is True
        assert client.redis._store["key3"] == '[1, 2, 3]'

    def test_set_non_serializable_raises_bug_exception(self):
        client = make_client()
        with pytest.raises(BugException, match="Data to store in cache not jsonable"):
            client.set("key4", object(), ttl=60)

    def test_set_ttl_zero_raises_bug_exception(self):
        client = make_client()
        with pytest.raises(BugException, match="TTL for redis is below 1"):
            client.set("key5", "value", ttl=0)

    def test_set_ttl_negative_raises_bug_exception(self):
        client = make_client()
        with pytest.raises(BugException, match="TTL for redis is below 1"):
            client.set("key5", "value", ttl=-10)

    def test_set_response_error_raises_bug_exception(self):
        client = make_client()
        client.redis.set_should_raise_response_error = True
        with pytest.raises(BugException, match="Error when setting data in redis"):
            client.set("key6", "value", ttl=60)

    def test_set_nx_acquires_when_key_absent(self):
        client = make_client()
        result = client.set("lock_key", "token1", ttl=60, nx=True)
        assert result is True

    def test_set_nx_rejects_when_key_exists(self):
        client = make_client()
        client.set("lock_key", "token1", ttl=60)
        result = client.set("lock_key", "token2", ttl=60, nx=True)
        assert result is False

    def test_set_without_nx_overwrites(self):
        client = make_client()
        client.set("key", "value1", ttl=60)
        result = client.set("key", "value2", ttl=60)
        assert result is True
        assert client.redis._store["key"] == "value2"


# ===========================================================================
# Tests: get
# ===========================================================================

class TestGet:
    def test_get_existing_string_returns_string(self):
        client = make_client()
        client.redis.get_return_value = "hello"
        result = client.get("key1", str)
        assert result == "hello"

    def test_get_existing_dict_returns_dict(self):
        client = make_client()
        client.redis.get_return_value = '{"a": 1}'
        result = client.get("key2", dict)
        assert result == {"a": 1}

    def test_get_existing_list_returns_list(self):
        client = make_client()
        client.redis.get_return_value = '[1, 2, 3]'
        result = client.get("key3", list)
        assert result == [1, 2, 3]

    def test_get_missing_key_returns_none(self):
        client = make_client()
        client.redis.get_return_value = None
        result = client.get("missing", str)
        assert result is None

    def test_get_invalid_json_for_dict_raises_bug_exception(self):
        client = make_client()
        client.redis.get_return_value = "not-a-json"
        with pytest.raises(BugException, match="list/dict stored in redis is not a Json"):
            client.get("key4", dict)

    def test_get_invalid_json_for_list_raises_bug_exception(self):
        client = make_client()
        client.redis.get_return_value = "not-a-json"
        with pytest.raises(BugException, match="list/dict stored in redis is not a Json"):
            client.get("key5", list)


# ===========================================================================
# Tests: hashset
# ===========================================================================

class TestHashset:
    def test_hashset_returns_true(self):
        client = make_client()
        result = client.hashset("session:abc", {"uid": "user1", "domain": "example.com"}, ttl=300)
        assert result is True

    def test_hashset_stores_data(self):
        client = make_client()
        data = {"uid": "user1", "last_activity": "1234567890"}
        client.hashset("session:abc", data, ttl=300)
        assert client.redis._hashes["session:abc"]["uid"] == "user1"

    def test_hashset_ttl_zero_skips_expire(self):
        client = make_client()
        with patch.object(client.redis, "expire") as mock_expire:
            client.hashset("session:abc", {"uid": "user1"}, ttl=0)
            mock_expire.assert_not_called()

    def test_hashset_positive_ttl_calls_expire(self):
        client = make_client()
        with patch.object(client.redis, "expire") as mock_expire:
            client.hashset("session:abc", {"uid": "user1"}, ttl=300)
            mock_expire.assert_called_once_with("session:abc", 300)


# ===========================================================================
# Tests: hashget
# ===========================================================================

class TestHashget:
    def test_hashget_existing_key_returns_dict(self):
        client = make_client()
        client.redis._hashes["session:abc"] = {"uid": "user1", "domain": "example.com"}
        result = client.hashget("session:abc")
        assert result == {"uid": "user1", "domain": "example.com"}

    def test_hashget_missing_key_returns_empty_dict(self):
        client = make_client()
        result = client.hashget("session:missing")
        # hgetall returns {} for missing keys; cast to dict|None gives {}
        assert result == {} or result is None


# ===========================================================================
# Tests: zset_add
# ===========================================================================

class TestZsetAdd:
    def test_zset_add_inserts_member(self):
        client = make_client()
        client.zset_add("myzset", "member1", 1000.0)
        assert "member1" in client.redis._zsets.get("myzset", {})

    def test_zset_add_updates_score(self):
        client = make_client()
        client.zset_add("myzset", "member1", 1000.0)
        client.zset_add("myzset", "member1", 2000.0)
        assert client.redis._zsets["myzset"]["member1"] == 2000.0


# ===========================================================================
# Tests: zset_remove
# ===========================================================================

class TestZsetRemove:
    def test_zset_remove_existing_member(self):
        client = make_client()
        client.redis._zsets["myzset"] = {"member1": 1.0, "member2": 2.0}
        removed = client.zset_remove("myzset", "member1")
        assert removed == 1
        assert "member1" not in client.redis._zsets["myzset"]

    def test_zset_remove_multiple_members(self):
        client = make_client()
        client.redis._zsets["myzset"] = {"m1": 1.0, "m2": 2.0, "m3": 3.0}
        removed = client.zset_remove("myzset", "m1", "m2")
        assert removed == 2

    def test_zset_remove_nonexistent_member_returns_zero(self):
        client = make_client()
        client.redis._zsets["myzset"] = {}
        removed = client.zset_remove("myzset", "ghost")
        assert removed == 0


# ===========================================================================
# Tests: zset_count
# ===========================================================================

class TestZsetCount:
    def test_zset_count_returns_cardinality(self):
        client = make_client()
        client.redis._zsets["myzset"] = {"m1": 1.0, "m2": 2.0}
        assert client.zset_count("myzset") == 2

    def test_zset_count_empty_set_returns_zero(self):
        client = make_client()
        assert client.zset_count("nonexistent") == 0


# ===========================================================================
# Tests: delete
# ===========================================================================

class TestDelete:
    def test_delete_existing_key(self):
        client = make_client()
        client.redis._store["k1"] = "v1"
        ret = client.delete("k1")
        assert ret == 1

    def test_delete_multiple_keys(self):
        client = make_client()
        client.redis._hashes["h1"] = {"a": "1"}
        client.redis._hashes["h2"] = {"b": "2"}
        ret = client.delete("h1", "h2")
        assert ret == 2

    def test_delete_missing_key_returns_zero(self):
        client = make_client()
        ret = client.delete("ghost")
        assert ret == 0


# ===========================================================================
# Tests: _pipeline_hgetall
# ===========================================================================

class TestPipelineHgetall:
    def _make_client_with_pipeline(self, pipeline_results, zset_data=None):
        """Build a client whose pipeline.execute() returns pipeline_results."""
        client = make_client()
        fake_pipe = FakePipeline(results=pipeline_results)
        client.redis.pipeline = MagicMock(return_value=fake_pipe)
        # Also wire up zrem on the raw redis for lazy cleanup
        client.redis.zrem = MagicMock(return_value=1)
        if zset_data is not None:
            client.redis._zsets = zset_data
        return client

    def test_returns_items_injecting_session_key(self):
        data = {
            cs.USER_UID: "user1",
            cs.USER_DOMAIN: "example.com",
            cs.SESSION_SENSITIVE: "secret",
        }
        client = self._make_client_with_pipeline([data])
        items = client._pipeline_hgetall(["session:abc"])
        assert len(items) == 1
        assert items[0][cs.SESSION_KEY] == "session:abc"
        # SESSION_SENSITIVE must be stripped
        assert cs.SESSION_SENSITIVE not in items[0]

    def test_empty_hash_treated_as_orphan(self):
        """Keys with empty hashes are removed from sorted-set indexes."""
        # Two keys: first has data, second is expired (empty dict)
        good_data = {cs.USER_UID: "user1", cs.SESSION_SENSITIVE: "s"}
        client = self._make_client_with_pipeline([good_data, {}])
        # Provide a second fake pipeline for cleanup
        cleanup_pipe = FakePipeline(results=[1, 1, 1])
        side_effects = [FakePipeline(results=[good_data, {}]), cleanup_pipe]
        client.redis.pipeline = MagicMock(side_effect=side_effects)
        items = client._pipeline_hgetall(["session:abc", "session:orphan"])
        assert len(items) == 1
        assert items[0][cs.SESSION_KEY] == "session:abc"

    def test_empty_keys_list_returns_empty(self):
        client = self._make_client_with_pipeline([])
        items = client._pipeline_hgetall([])
        assert items == []


# ===========================================================================
# Tests: zset_paginate_hashes
# ===========================================================================

class TestZsetPaginateHashes:
    def _make_paginate_client(self, session_hashes: dict, zset_members: list | None = None):
        """
        Build a client pre-loaded with hash data and a default activity zset.
        The pipeline used by _pipeline_hgetall is replaced by one that returns
        the actual hash dicts stored in _hashes (matching the requested key order).

        session_hashes: dict mapping redis key -> hash dict (must include SESSION_SENSITIVE)
        zset_members: ordered list of keys for ZSET_USER_SESSIONS_ACTIVITY (default: list(session_hashes.keys()))
        """
        client = make_client()
        hashes_copy = {k: dict(v) for k, v in session_hashes.items()}
        client.redis._hashes = hashes_copy

        members = zset_members if zset_members is not None else list(session_hashes.keys())
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {m: float(i) for i, m in enumerate(members)}

        # Also populate the UID/domain zsets with the same members so fast-path
        # sort_by tests can resolve them.
        client.redis._zsets[cs.ZSET_USER_SESSIONS_UID] = {m: float(i) for i, m in enumerate(members)}
        client.redis._zsets[cs.ZSET_USER_SESSIONS_DOMAIN] = {m: float(i) for i, m in enumerate(members)}

        # Replace pipeline() so _pipeline_hgetall gets real hash data.
        # Each call to pipeline() produces a fresh FakePipeline whose execute()
        # returns the hashes for the keys that were queued via hgetall().
        original_hashes = hashes_copy

        class _DataPipeline:
            """Pipeline that resolves hgetall() calls against the stored hashes."""
            def __init__(self):
                self._keys: list[str] = []

            def hgetall(self, key):
                self._keys.append(key)
                return self

            def hget(self, key, field):
                return self

            def delete(self, key):
                return self

            def zrem(self, zset_key, member):
                return self

            def execute(self):
                # If hgetall keys were queued, return their hash dicts.
                # Otherwise (cleanup pipeline) return a list of 1s.
                if self._keys:
                    return [dict(original_hashes.get(k, {})) for k in self._keys]
                return [1]

        client.redis.pipeline = MagicMock(side_effect=lambda transaction=True: _DataPipeline())
        return client

    def test_empty_zset_returns_zero_and_empty_list(self):
        client = make_client()
        # No zset data at all
        result = client.zset_paginate_hashes()
        assert result == (0, [])

    def test_returns_all_items_by_default(self):
        hashes = {
            "session:1": {cs.USER_UID: "u1", cs.SESSION_SENSITIVE: "s"},
            "session:2": {cs.USER_UID: "u2", cs.SESSION_SENSITIVE: "s"},
        }
        client = self._make_paginate_client(hashes)
        total, items = client.zset_paginate_hashes()
        assert total == 2
        assert len(items) == 2

    def test_pagination_with_first_and_last(self):
        hashes = {
            "session:1": {cs.USER_UID: "u1", cs.SESSION_SENSITIVE: "s"},
            "session:2": {cs.USER_UID: "u2", cs.SESSION_SENSITIVE: "s"},
            "session:3": {cs.USER_UID: "u3", cs.SESSION_SENSITIVE: "s"},
        }
        client = self._make_paginate_client(hashes, zset_members=["session:1", "session:2", "session:3"])
        total, items = client.zset_paginate_hashes(first=0, last=1)
        assert total == 3
        assert len(items) == 2

    def test_sort_by_dedicated_zset_index(self):
        """Sorting by USER_UID should use ZSET_USER_SESSIONS_UID fast path."""
        hashes = {
            "session:1": {cs.USER_UID: "alice", cs.SESSION_SENSITIVE: "s"},
            "session:2": {cs.USER_UID: "bob", cs.SESSION_SENSITIVE: "s"},
        }
        client = self._make_paginate_client(hashes)
        # Populate the UID zset
        client.redis._zsets[cs.ZSET_USER_SESSIONS_UID] = {
            "session:1": 0.0,
            "session:2": 1.0,
        }
        total, items = client.zset_paginate_hashes(sort_by=cs.USER_UID, sort_order="asc")
        assert total == 2
        assert len(items) == 2

    def test_sort_by_unknown_field_uses_in_memory_fallback(self):
        hashes = {
            "session:1": {cs.USER_UID: "u1", "custom_field": "z", cs.SESSION_SENSITIVE: "s"},
            "session:2": {cs.USER_UID: "u2", "custom_field": "a", cs.SESSION_SENSITIVE: "s"},
        }
        client = self._make_paginate_client(hashes, zset_members=["session:1", "session:2"])
        total, items = client.zset_paginate_hashes(sort_by="custom_field", sort_order="asc")
        assert total == 2
        # Items sorted ascending by custom_field: "a" first
        assert items[0]["custom_field"] == "a"

    def test_include_fields_returns_all_non_sensitive_fields(self):
        hashes = {
            "session:1": {cs.USER_UID: "u1", cs.USER_DOMAIN: "example.com", cs.SESSION_SENSITIVE: "s"},
        }
        client = self._make_paginate_client(hashes)
        total, items = client.zset_paginate_hashes()
        assert total == 1
        assert cs.USER_UID in items[0]
        assert cs.USER_DOMAIN in items[0]

    def test_sensitive_data_stripped_from_items(self):
        hashes = {
            "session:1": {cs.USER_UID: "u1", cs.SESSION_SENSITIVE: "topsecret"},
        }
        client = self._make_paginate_client(hashes)
        total, items = client.zset_paginate_hashes()
        assert cs.SESSION_SENSITIVE not in items[0]


# ===========================================================================
# Tests: revoke_user_sessions_by_uid
# ===========================================================================

class TestRevokeUserSessionsByUid:
    def test_no_active_sessions_returns_zero(self):
        client = make_client()
        # Empty activity zset
        result = client.revoke_user_sessions_by_uid(["user1"])
        assert result == 0

    def test_revokes_matching_sessions(self):
        client = make_client()
        # Populate activity zset
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {
            "session:1": 1000.0,
            "session:2": 2000.0,
        }
        # hget pipeline returns uid for each key in order
        client.redis.pipeline_results = ["user1", "user2"]
        # Capture final pipeline calls
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            fetch_pipe = FakePipeline(results=["user1", "user2"])
            delete_pipe = FakePipeline(results=[1, 1, 1, 1])
            mock_pipeline.side_effect = [fetch_pipe, delete_pipe]
            result = client.revoke_user_sessions_by_uid(["user1"])
        assert result == 1

    def test_no_matching_uid_returns_zero(self):
        client = make_client()
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {"session:1": 1000.0}
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            fetch_pipe = FakePipeline(results=["other_user"])
            mock_pipeline.return_value = fetch_pipe
            result = client.revoke_user_sessions_by_uid(["user1"])
        assert result == 0

    def test_revokes_multiple_uids(self):
        client = make_client()
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {
            "session:1": 1.0,
            "session:2": 2.0,
            "session:3": 3.0,
        }
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            fetch_pipe = FakePipeline(results=["user1", "user2", "user3"])
            # 3 sessions revoked → 3×4 = 12 results; every 4th (index 0,4,8) is 1 (deleted)
            delete_pipe = FakePipeline(results=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
            mock_pipeline.side_effect = [fetch_pipe, delete_pipe]
            result = client.revoke_user_sessions_by_uid(["user1", "user2", "user3"])
        assert result == 3


# ===========================================================================
# Tests: revoke_user_sessions_by_key
# ===========================================================================

class TestRevokeUserSessionsByKey:
    def test_empty_list_returns_zero(self):
        client = make_client()
        result = client.revoke_user_sessions_by_key([])
        assert result == 0

    def test_revokes_given_keys(self):
        client = make_client()
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            # 2 keys × 4 commands each = 8 results; results[0]=1 and results[4]=1 → 2 revoked
            pipe = FakePipeline(results=[1, 1, 1, 1, 1, 1, 1, 1])
            mock_pipeline.return_value = pipe
            result = client.revoke_user_sessions_by_key(["session:1", "session:2"])
        assert result == 2

    def test_already_deleted_key_not_counted(self):
        client = make_client()
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            # Only first key was actually present (delete returned 1 for first, 0 for second)
            pipe = FakePipeline(results=[1, 1, 1, 1, 0, 1, 1, 1])
            mock_pipeline.return_value = pipe
            result = client.revoke_user_sessions_by_key(["session:1", "session:ghost"])
        assert result == 1

    def test_pipeline_called_with_correct_commands(self):
        client = make_client()
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            fake_pipe = MagicMock()
            fake_pipe.execute.return_value = [1, 1, 1, 1]
            mock_pipeline.return_value = fake_pipe
            client.revoke_user_sessions_by_key(["session:1"])
        fake_pipe.delete.assert_called_once_with("session:1")
        assert fake_pipe.zrem.call_count == 3


# ===========================================================================
# Tests: revoke_user_sessions_by_activity
# ===========================================================================

class TestRevokeUserSessionsByActivity:
    def test_no_old_sessions_returns_zero(self):
        client = make_client()
        # No sessions in zset at all
        result = client.revoke_user_sessions_by_activity(9999999999)
        assert result == 0

    def test_revokes_sessions_older_than_timestamp(self):
        client = make_client()
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {
            "session:old": 100.0,
            "session:new": 9999.0,
        }
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            # 1 session revoked → 4 results; results[0]=1
            pipe = FakePipeline(results=[1, 1, 1, 1])
            mock_pipeline.return_value = pipe
            result = client.revoke_user_sessions_by_activity(500)
        assert result == 1

    def test_no_sessions_below_timestamp_returns_zero(self):
        client = make_client()
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {
            "session:new": 99999.0,
        }
        result = client.revoke_user_sessions_by_activity(100)
        assert result == 0

    def test_all_sessions_revoked_when_all_old(self):
        client = make_client()
        client.redis._zsets[cs.ZSET_USER_SESSIONS_ACTIVITY] = {
            "session:1": 10.0,
            "session:2": 20.0,
        }
        with patch.object(client.redis, "pipeline") as mock_pipeline:
            # 2 sessions × 3 commands (delete + 2×zrem) + 1 zremrangebyscore = 7 results
            # delete results at indices 0 and 3
            pipe = FakePipeline(results=[1, 1, 1, 1, 1, 1, 1])
            mock_pipeline.return_value = pipe
            result = client.revoke_user_sessions_by_activity(50)
        assert result == 2


# ===========================================================================
# Tests: SORT_FIELD_TO_ZSET mapping
# ===========================================================================

class TestSortFieldToZset:
    def test_mapping_contains_expected_keys(self):
        assert cs.SESSION_LAST_SEEN in SORT_FIELD_TO_ZSET
        assert cs.USER_UID in SORT_FIELD_TO_ZSET
        assert cs.USER_DOMAIN in SORT_FIELD_TO_ZSET

    def test_mapping_values_are_correct_zsets(self):
        assert SORT_FIELD_TO_ZSET[cs.SESSION_LAST_SEEN] == cs.ZSET_USER_SESSIONS_ACTIVITY
        assert SORT_FIELD_TO_ZSET[cs.USER_UID] == cs.ZSET_USER_SESSIONS_UID
        assert SORT_FIELD_TO_ZSET[cs.USER_DOMAIN] == cs.ZSET_USER_SESSIONS_DOMAIN
