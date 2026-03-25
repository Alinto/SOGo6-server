"""
Tests unitaires pour InterfaceApiAdminUser (Interface layer).
Ces tests utilisent un fake ModuleAdminUser pour tester la logique de l'interface.
"""
from app.interface.admin.InterfaceApiAdminUser import InterfaceApiAdminUser
from app.utils.exceptions import RequestException
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


class FakeModuleAdminUser:
    """Fake ModuleAdminUser for testing InterfaceApiAdminUser."""

    def __init__(self):
        # Tracking
        self.get_active_users_args = None
        self.revoke_users_args = None
        self.revoke_inactive_users_args = None

        # Results
        self.get_active_users_result = (
            3,
            [
                {"uid": "user1", "last_activity": 1700000001},
                {"uid": "user2", "last_activity": 1700000002},
                {"uid": "user3", "last_activity": 1700000003},
            ],
        )
        self.revoke_users_result = 2
        self.revoke_inactive_users_result = 1

    def get_active_users(self, collection_param):
        """Get active users."""
        self.get_active_users_args = (
            collection_param.first_item,
            collection_param.last_item,
            collection_param.sort_by,
            collection_param.sort_order,
            collection_param.fields,
        )
        return self.get_active_users_result

    def revoke_users(self, uids=None, redis_keys=None):
        """Revoke users."""
        self.revoke_users_args = (uids, redis_keys)
        return self.revoke_users_result

    def revoke_inactive_users(self, timestamp):
        """Revoke inactive users."""
        self.revoke_inactive_users_args = timestamp
        return self.revoke_inactive_users_result


def patch_module_on_interface(monkeypatch, fake_module):
    """Patch ModuleAdminUser in InterfaceApiAdminUser module."""
    monkeypatch.setattr(
        "app.interface.admin.InterfaceApiAdminUser.ModuleAdminUser",
        lambda: fake_module,
    )


# ========== Tests for get_active_users ==========

def test_get_active_users_success(monkeypatch):
    """Test getting active users with default parameters."""
    fake_module = FakeModuleAdminUser()
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    total_count, result, status_code = interface.get_active_users(
        CollectionPaginateArgs(page=1, page_size=11)
    )

    assert status_code == 200
    assert total_count == 3
    assert len(result["data"]) == 3
    assert result["data"][0]["uid"] == "user1"
    assert fake_module.get_active_users_args[0] == 0   # first
    assert fake_module.get_active_users_args[1] == 10  # last


def test_get_active_users_with_sort(monkeypatch):
    """Test getting active users with sort parameters."""
    fake_module = FakeModuleAdminUser()
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    total_count, _result, status_code = interface.get_active_users(
        CollectionPaginateArgs(page=1, page_size=6, sort_by="uid", sort_order="asc", fields="uid,last_activity")
    )

    assert status_code == 200
    assert total_count == 3
    assert fake_module.get_active_users_args[2] == "uid"              # sort_by
    assert fake_module.get_active_users_args[3] == "asc"              # sort_order
    assert fake_module.get_active_users_args[4] == "uid,last_activity"  # include_fields


def test_get_active_users_request_exception(monkeypatch):
    """Test error handling when get_active_users raises a RequestException."""
    fake_module = FakeModuleAdminUser()
    fake_module.get_active_users = lambda collection_param: (_ for _ in ()).throw(
        RequestException("Cache scan failed", err.ERROR_CACHE_SCAN_FAILED)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    total_count, result, status_code = interface.get_active_users(
        CollectionPaginateArgs(page=1, page_size=11)
    )

    assert status_code == 500
    assert total_count == 0
    assert result["error_code"] == err.ERROR_CACHE_SCAN_FAILED.c


def test_get_active_users_no_results(monkeypatch):
    """Test getting active users when there are none."""
    fake_module = FakeModuleAdminUser()
    fake_module.get_active_users_result = (0, [])
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    total_count, result, status_code = interface.get_active_users(
        CollectionPaginateArgs(page=1, page_size=11)
    )

    assert status_code == 200
    assert total_count == 0
    assert result["data"] == []


# ========== Tests for revoke_users ==========

def test_revoke_users_by_uid_success(monkeypatch):
    """Test revoking users by UID."""
    fake_module = FakeModuleAdminUser()
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_users(uids=["user1", "user2"])

    assert status_code == 200
    assert result["data"]["revoked"] == 2
    assert fake_module.revoke_users_args == (["user1", "user2"], None)


def test_revoke_users_by_redis_key_success(monkeypatch):
    """Test revoking users by Redis key."""
    fake_module = FakeModuleAdminUser()
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_users(redis_keys=["key1", "key2"])

    assert status_code == 200
    assert result["data"]["revoked"] == 2
    assert fake_module.revoke_users_args == (None, ["key1", "key2"])


def test_revoke_users_invalid_body(monkeypatch):
    """Test error when neither uids nor redis_keys is provided."""
    fake_module = FakeModuleAdminUser()
    fake_module.revoke_users = lambda **kwargs: (_ for _ in ()).throw(
        RequestException(
            "Exactly one of 'uid' or 'redis_key' must be provided",
            err.ERROR_REVOKE_BODY_INVALID,
        )
    )
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_users()

    assert status_code == 400
    assert result["error_code"] == err.ERROR_REVOKE_BODY_INVALID.c


def test_revoke_users_cache_failure(monkeypatch):
    """Test error when the cache revocation fails."""
    fake_module = FakeModuleAdminUser()
    fake_module.revoke_users = lambda **kwargs: (_ for _ in ()).throw(
        RequestException("Cache revoke failed", err.ERROR_CACHE_REVOKE_FAILED)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_users(uids=["user1"])

    assert status_code == 500
    assert result["error_code"] == err.ERROR_CACHE_REVOKE_FAILED.c


def test_revoke_users_by_key_cache_failure(monkeypatch):
    """Test error when the cache revocation by key fails."""
    fake_module = FakeModuleAdminUser()
    fake_module.revoke_users = lambda **kwargs: (_ for _ in ()).throw(
        RequestException("Cache revoke by key failed", err.ERROR_CACHE_REVOKE_KEY_FAILED)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_users(redis_keys=["key1"])

    assert status_code == 500
    assert result["error_code"] == err.ERROR_CACHE_REVOKE_KEY_FAILED.c


# ========== Tests for revoke_inactive_users ==========

def test_revoke_inactive_users_success(monkeypatch):
    """Test revoking inactive users older than a given timestamp."""
    fake_module = FakeModuleAdminUser()
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_inactive_users(timestamp=1700000000)

    assert status_code == 200
    assert result["data"]["revoked"] == 1
    assert fake_module.revoke_inactive_users_args == 1700000000


def test_revoke_inactive_users_none_revoked(monkeypatch):
    """Test revoking inactive users when there are none to revoke."""
    fake_module = FakeModuleAdminUser()
    fake_module.revoke_inactive_users_result = 0
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_inactive_users(timestamp=1700000000)

    assert status_code == 200
    assert result["data"]["revoked"] == 0


def test_revoke_inactive_users_cache_failure(monkeypatch):
    """Test error when the inactive cache revocation fails."""
    fake_module = FakeModuleAdminUser()
    fake_module.revoke_inactive_users = lambda timestamp: (_ for _ in ()).throw(
        RequestException("Cache revoke inactive failed", err.ERROR_CACHE_REVOKE_INACTIVE_FAILED)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    interface = InterfaceApiAdminUser(process_setting=None)

    result, status_code = interface.revoke_inactive_users(timestamp=1700000000)

    assert status_code == 500
    assert result["error_code"] == err.ERROR_CACHE_REVOKE_INACTIVE_FAILED.c
