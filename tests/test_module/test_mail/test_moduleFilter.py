"""
Tests unitaires pour ModuleFilter (Module layer).
Ces tests utilisent des fakes pour ClientSQL et ClientFiltering pour tester
la logique métier du module sans dépendances externes.
"""
import pytest
from unittest.mock import MagicMock
from app.module.mail.ModuleFilter import ModuleFilter
from app.utils.exceptions import RequestException, BugException


class FakeClientFiltering:
    """Fake ClientFiltering for testing ModuleFilter."""

    def __init__(self):
        self.connected = False
        self.logged_in = False
        self.logged_out = False
        self.set_merged_filters_calls = []
        self.set_merged_filters_result = {}  # empty dict = no section activated
        self.set_merged_filters_raises = None
        self.connect_raises = None
        self.login_raises = None

    def connect(self):
        if self.connect_raises is not None:
            raise self.connect_raises
        self.connected = True

    def login(self, username, password):
        if self.login_raises is not None:
            raise self.login_raises
        self.logged_in = True

    def logout(self):
        self.logged_out = True

    def set_merged_filters(self, filters_dict):
        self.set_merged_filters_calls.append(dict(filters_dict))
        if self.set_merged_filters_raises is not None:
            raise self.set_merged_filters_raises
        return self.set_merged_filters_result


class FakeClientSQL:
    """Fake ClientSQL for testing ModuleFilter."""

    def __init__(self, initial_filters=None):
        self.connected = False
        self.stored_filters = initial_filters if initial_filters is not None else {}
        # When set, overrides the returned rows from select_from_table
        self.select_result_override = None
        self.select_raises = None
        self.update_result = True  # truthy = success
        self.update_raises = None
        self.update_calls = []

    def connect(self):
        self.connected = True

    def select_from_table(self, table_name, column_tuple, condition):
        if self.select_raises is not None:
            raise self.select_raises
        if self.select_result_override is not None:
            return self.select_result_override
        return [(self.stored_filters,)]

    def update_in_table(self, table_name, column_tuple, values_list, condition):
        if self.update_raises is not None:
            raise self.update_raises
        self.update_calls.append(dict(values_list[0]))
        if self.update_result:
            self.stored_filters = values_list[0]
        return self.update_result


def _make_module(monkeypatch, fake_db=None, fake_filter_client=None):
    """Create a ModuleFilter with mocked dependencies."""
    if fake_db is None:
        fake_db = FakeClientSQL()
    if fake_filter_client is None:
        fake_filter_client = FakeClientFiltering()

    mock_user = MagicMock()
    mock_user.uid = 'test_user_123'
    mock_user.login_mail_filtering = 'user@example.com'
    mock_user.password = 'secret'

    mock_mail_settings = MagicMock()
    mock_mail_settings.SOGO_D_MAIL_FILTERING_TYPE = 'sieve'
    mock_mail_settings.get_mail_filtering_settings_for_type.return_value = {}

    mock_process_settings = MagicMock()
    mock_process_settings.SOGO_P_DB_TYPE = 'PostgreSQL'
    mock_process_settings.get_db_settings.return_value = {}

    # Patch import_and_instantiate_manager so that __init__ receives our fake DB
    monkeypatch.setattr(
        'app.module.mail.ModuleFilter.import_and_instantiate_manager',
        lambda *args, **kwargs: fake_db,
    )

    module = ModuleFilter(
        user=mock_user,
        mail_settings=mock_mail_settings,
        process_settings=mock_process_settings,
    )

    # Patch _open_filtering_client to always return our fake filtering client
    monkeypatch.setattr(module, '_open_filtering_client', lambda: fake_filter_client)

    return module, fake_db, fake_filter_client


# ========== Tests for initialization ==========

def test_module_init_success(monkeypatch):
    """Test ModuleFilter initialization with valid mocked objects."""
    fake_db = FakeClientSQL()
    mock_user = MagicMock()
    mock_mail_settings = MagicMock()
    mock_process_settings = MagicMock()
    mock_process_settings.SOGO_P_DB_TYPE = 'PostgreSQL'
    mock_process_settings.get_db_settings.return_value = {}

    monkeypatch.setattr(
        'app.module.mail.ModuleFilter.import_and_instantiate_manager',
        lambda *args, **kwargs: fake_db,
    )

    module = ModuleFilter(
        user=mock_user,
        mail_settings=mock_mail_settings,
        process_settings=mock_process_settings,
    )

    assert module.user is mock_user
    assert module.mail_settings is mock_mail_settings
    assert module.process_settings is mock_process_settings
    assert module.sogo_db_manager is fake_db


def test_module_init_without_args_raises():
    """Test that ModuleFilter raises TypeError when no arguments are provided."""
    with pytest.raises(TypeError):
        ModuleFilter()


# ========== Tests for _is_section_enabled (static method) ==========

def test_is_section_enabled_list_with_one_enabled_filter():
    """A list with at least one enabled filter is considered active."""
    value = [{"enabled": 1, "name": "rule1"}, {"enabled": 0, "name": "rule2"}]
    assert ModuleFilter._is_section_enabled(value) is True


def test_is_section_enabled_list_all_disabled():
    """A list where all filters are explicitly disabled is considered inactive."""
    value = [{"enabled": 0, "name": "rule1"}, {"enabled": 0, "name": "rule2"}]
    assert ModuleFilter._is_section_enabled(value) is False


def test_is_section_enabled_empty_list():
    """An empty list is considered inactive."""
    assert ModuleFilter._is_section_enabled([]) is False


def test_is_section_enabled_list_no_enabled_key_defaults_to_active():
    """A filter dict without 'enabled' key defaults to enabled=1 (active)."""
    value = [{"name": "rule_without_flag"}]
    assert ModuleFilter._is_section_enabled(value) is True


def test_is_section_enabled_dict_enabled():
    """A dict with enabled=1 is considered active."""
    value = {"enabled": 1, "days": 7}
    assert ModuleFilter._is_section_enabled(value) is True


def test_is_section_enabled_dict_disabled():
    """A dict with enabled=0 is considered inactive."""
    value = {"enabled": 0, "days": 7}
    assert ModuleFilter._is_section_enabled(value) is False


def test_is_section_enabled_dict_no_enabled_key_defaults_to_inactive():
    """A dict without 'enabled' key defaults to enabled=0 (inactive)."""
    value = {"days": 7}
    assert ModuleFilter._is_section_enabled(value) is False


def test_is_section_enabled_empty_dict():
    """An empty dict is considered inactive."""
    assert ModuleFilter._is_section_enabled({}) is False


def test_is_section_enabled_non_dict_non_list_values():
    """Non-dict, non-list values are considered inactive."""
    assert ModuleFilter._is_section_enabled(None) is False
    assert ModuleFilter._is_section_enabled("string") is False
    assert ModuleFilter._is_section_enabled(42) is False


# ========== Tests for get_section ==========

def test_get_section_returns_existing_section(monkeypatch):
    """get_section returns the stored value for an existing section key."""
    vacation_data = {"enabled": 1, "days": 7, "subject": "Away"}
    fake_db = FakeClientSQL(initial_filters={"vacation": vacation_data})
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    result = module.get_section("vacation")

    assert result == vacation_data


def test_get_section_missing_key_returns_none(monkeypatch):
    """get_section returns None when the section key does not exist."""
    fake_db = FakeClientSQL(initial_filters={})
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    result = module.get_section("vacation")

    assert result is None


def test_get_section_null_filters_in_db_treated_as_empty(monkeypatch):
    """get_section handles NULL filters column in DB (treated as empty dict)."""
    fake_db = FakeClientSQL()
    fake_db.select_result_override = [(None,)]  # NULL column value
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    result = module.get_section("vacation")

    assert result is None


def test_get_section_user_not_found_raises(monkeypatch):
    """get_section raises RequestException when the user profile row is missing."""
    fake_db = FakeClientSQL()
    fake_db.select_result_override = []  # empty result set = no user row
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    with pytest.raises(RequestException):
        module.get_section("filters")


def test_get_section_connects_db(monkeypatch):
    """get_section always calls connect() on the DB manager before reading."""
    fake_db = FakeClientSQL(initial_filters={"filters": []})
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    assert not fake_db.connected
    module.get_section("filters")
    assert fake_db.connected


def test_get_section_filters_key(monkeypatch):
    """get_section returns the filters list for the 'filters' section key."""
    filters_data = [{"enabled": 1, "name": "rule1"}]
    fake_db = FakeClientSQL(initial_filters={"filters": filters_data})
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    result = module.get_section("filters")

    assert result == filters_data


# ========== Tests for set_section - Sieve sections ==========

def test_set_section_filters_pushes_to_sieve_and_persists(monkeypatch):
    """set_section for 'filters' pushes to Sieve and persists to DB."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"filters": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    filters_value = [{"enabled": 1, "name": "rule1"}]
    result = module.set_section("filters", filters_value)

    assert result["filters"] == filters_value
    assert len(fake_client.set_merged_filters_calls) == 1
    assert len(fake_db.update_calls) == 1
    assert fake_db.update_calls[0]["filters"] == filters_value


def test_set_section_vacation_pushes_to_sieve_and_persists(monkeypatch):
    """set_section for 'vacation' pushes to Sieve and persists to DB."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"vacation": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    vacation_value = {"enabled": 1, "days": 7, "subject": "On vacation"}
    result = module.set_section("vacation", vacation_value)

    assert result["vacation"] == vacation_value
    assert len(fake_client.set_merged_filters_calls) == 1


def test_set_section_forward_pushes_to_sieve_and_persists(monkeypatch):
    """set_section for 'forward' pushes to Sieve and persists to DB."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"forward": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    forward_value = {"enabled": 1, "destination": "other@example.com"}
    result = module.set_section("forward", forward_value)

    assert result["forward"] == forward_value
    assert len(fake_client.set_merged_filters_calls) == 1


def test_set_section_notification_pushes_to_sieve_and_persists(monkeypatch):
    """set_section for 'notification' pushes to Sieve and persists to DB."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"notification": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    notification_value = {"enabled": 1, "method": "mailto"}
    result = module.set_section("notification", notification_value)

    assert result["notification"] == notification_value
    assert len(fake_client.set_merged_filters_calls) == 1


def test_set_section_disabled_section_still_calls_sieve(monkeypatch):
    """A disabled section still calls Sieve (to rebuild the merged script) and is persisted."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    # Sieve returns nothing activated (disabled section removed from script)
    fake_client.set_merged_filters_result = {}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    vacation_disabled = {"enabled": 0, "days": 7, "subject": "Away"}
    result = module.set_section("vacation", vacation_disabled)

    # Sieve was called to rebuild the merged script
    assert len(fake_client.set_merged_filters_calls) == 1
    # Section is disabled → _is_section_enabled is False → NOT popped → still persisted
    assert result["vacation"] == vacation_disabled
    assert fake_db.update_calls[0]["vacation"] == vacation_disabled


def test_set_section_active_not_activated_by_sieve_is_not_persisted(monkeypatch):
    """Active section not activated by Sieve (e.g. missing extension) is NOT persisted to DB."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    # Sieve does not report 'notification' as activated (missing enotify extension)
    fake_client.set_merged_filters_result = {}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    notification_value = {"enabled": 1, "method": "mailto"}
    result = module.set_section("notification", notification_value)

    # The section must NOT appear in the returned dict
    assert "notification" not in result
    # The DB update must have been called but without the 'notification' key
    assert len(fake_db.update_calls) == 1
    assert "notification" not in fake_db.update_calls[0]


def test_set_section_sieve_request_exception_propagates(monkeypatch):
    """set_section raises RequestException when Sieve communication fails."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_raises = RequestException("Sieve connection failed")
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    with pytest.raises(RequestException, match="Sieve connection failed"):
        module.set_section("filters", [{"enabled": 1}])

    # DB must NOT have been written
    assert len(fake_db.update_calls) == 0


def test_set_section_sieve_bug_exception_propagates(monkeypatch):
    """set_section raises BugException when a bug occurs in the filtering client."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_raises = BugException("Unexpected bug in Sieve")
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    with pytest.raises(BugException):
        module.set_section("filters", [{"enabled": 1}])

    # DB must NOT have been written
    assert len(fake_db.update_calls) == 0


def test_set_section_sieve_error_always_calls_logout(monkeypatch):
    """Even when Sieve raises, logout() is always called in the finally block."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_raises = RequestException("Sieve error")
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    with pytest.raises(RequestException):
        module.set_section("vacation", {"enabled": 1})

    assert fake_client.logged_out is True


def test_set_section_success_calls_logout(monkeypatch):
    """After a successful set_section, the filtering client logout() is always called."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"filters": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    module.set_section("filters", [{"enabled": 1}])

    assert fake_client.logged_out is True


def test_set_section_db_write_fails_raises(monkeypatch):
    """set_section raises RequestException when the DB update returns a falsy value."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_db.update_result = False  # simulate failed update (e.g. no rows affected)
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"vacation": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    with pytest.raises(RequestException):
        module.set_section("vacation", {"enabled": 1, "days": 7})


def test_set_section_user_not_found_raises(monkeypatch):
    """set_section raises RequestException when the user profile row is missing."""
    fake_db = FakeClientSQL()
    fake_db.select_result_override = []  # empty result set = no user row
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db)

    with pytest.raises(RequestException):
        module.set_section("filters", [])


def test_set_section_preserves_existing_sections(monkeypatch):
    """set_section updates one section without erasing others already in the DB."""
    existing_vacation = {"enabled": 1, "days": 3, "subject": "BRB"}
    fake_db = FakeClientSQL(initial_filters={"vacation": existing_vacation})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"filters": True, "vacation": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    new_filters = [{"enabled": 1, "name": "rule1"}]
    result = module.set_section("filters", new_filters)

    assert result["filters"] == new_filters
    assert result["vacation"] == existing_vacation


def test_set_section_null_filters_in_db_treated_as_empty(monkeypatch):
    """set_section handles a NULL filters column in DB (treated as an empty dict)."""
    fake_db = FakeClientSQL()
    fake_db.select_result_override = [(None,)]  # NULL column value in DB
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"vacation": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    vacation_value = {"enabled": 1, "days": 5}
    result = module.set_section("vacation", vacation_value)

    assert result["vacation"] == vacation_value


def test_set_section_passes_full_filters_dict_to_sieve(monkeypatch):
    """set_section passes the complete filters dict (all sections merged) to set_merged_filters."""
    existing_forward = {"enabled": 1, "destination": "other@example.com"}
    fake_db = FakeClientSQL(initial_filters={"forward": existing_forward})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"vacation": True, "forward": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    vacation_value = {"enabled": 1, "days": 7}
    module.set_section("vacation", vacation_value)

    # The dict passed to Sieve must contain both the new section and existing ones
    sieve_call_arg = fake_client.set_merged_filters_calls[0]
    assert sieve_call_arg["vacation"] == vacation_value
    assert sieve_call_arg["forward"] == existing_forward


def test_set_section_connects_db(monkeypatch):
    """set_section always calls connect() on the DB manager before reading."""
    fake_db = FakeClientSQL(initial_filters={})
    fake_client = FakeClientFiltering()
    fake_client.set_merged_filters_result = {"filters": True}
    module, _, _ = _make_module(monkeypatch, fake_db=fake_db, fake_filter_client=fake_client)

    assert not fake_db.connected
    module.set_section("filters", [{"enabled": 1}])
    assert fake_db.connected
