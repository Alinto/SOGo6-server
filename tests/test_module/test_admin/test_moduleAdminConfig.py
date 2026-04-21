"""
Tests unitaires pour ModuleAdminConfig (Module layer).
Ces tests utilisent un fake ClientSQL pour tester la logique métier du module.
"""

import pytest
from copy import deepcopy
from unittest.mock import MagicMock, patch

from app.module.admin.ModuleAdminConfig import ModuleAdminConfig, _compute_diff
from app.utils.exceptions import RequestException, AggravatedException, BugException
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

DOMAIN_ID = "example.com"

DEFAULT_DOMAIN_SETTINGS = {
    "SOGoLoginDomain": "example.com",
    "SOGoTimeZone": "UTC",
    "nested": {
        "key1": "value1",
        "key2": "value2",
    },
}

SYSTEM_SETTINGS = {
    "SOGoSMTPServer": "smtp.example.com",
    "SOGoIMAPServer": "imap.example.com",
}


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


# ---------------------------------------------------------------------------
# Fake ClientSQL
# ---------------------------------------------------------------------------

class FakeClientSQL:
    """Fake ClientSQL for testing ModuleAdminConfig."""

    def __init__(self):
        # Configurable results
        self.select_result = []          # list of tuples returned by select_from_table
        self.insert_result = 1
        self.update_result = 1
        self.delete_result = 1
        self.count_result = 0

        # Track method calls
        self.connect_calls = 0
        self.select_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []
        self.count_calls = []

    def connect(self):
        self.connect_calls += 1

    def select_from_table(self, table_name, column_tuple, condition=None, offset=None, limit=None, sort_by=None, order=None):
        self.select_calls.append({
            "table_name": table_name,
            "column_tuple": column_tuple,
            "condition": condition,
        })
        result = self.select_result
        if isinstance(result, BaseException):
            raise result
        return iter(result)

    def insert_in_table(self, table_name, column_tuple, values_tuple):
        self.insert_calls.append({
            "table_name": table_name,
            "column_tuple": column_tuple,
            "values_tuple": values_tuple,
        })
        result = self.insert_result
        if isinstance(result, BaseException):
            raise result
        return result

    def update_in_table(self, table_name, column_tuple, values_list, condition=None):
        self.update_calls.append({
            "table_name": table_name,
            "column_tuple": column_tuple,
            "values_list": values_list,
        })
        result = self.update_result
        if isinstance(result, BaseException):
            raise result
        return result

    def delete_row_in_table(self, table_name, condition, expected_row=1):
        self.delete_calls.append({
            "table_name": table_name,
            "condition": condition,
        })
        result = self.delete_result
        if isinstance(result, BaseException):
            raise result
        return result

    def count_row_in_table(self, table_name, condition=None):
        self.count_calls.append({"table_name": table_name})
        result = self.count_result
        if isinstance(result, BaseException):
            raise result
        return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _make_module(monkeypatch, fake_db=None):
    """Create a ModuleAdminConfig with a patched sogo_db_manager."""
    if fake_db is None:
        fake_db = FakeClientSQL()

    mock_process_settings = MagicMock()
    mock_process_settings.SOGO_P_DB_TYPE = "MySQL"
    mock_process_settings.get_db_settings.return_value = {}

    with patch("app.module.admin.ModuleAdminConfig.import_and_instantiate_manager", return_value=fake_db):
        module = ModuleAdminConfig(process_settings=mock_process_settings)

    return module, fake_db


# ===========================================================================
# Tests for _compute_diff (standalone function)
# ===========================================================================

def test_compute_diff_empty_dicts():
    """_compute_diff on two empty dicts returns empty dict."""
    assert _compute_diff({}, {}) == {}


def test_compute_diff_no_difference():
    """_compute_diff with identical dicts returns empty dict."""
    d = {"a": 1, "b": "x"}
    assert _compute_diff(d, d) == {}


def test_compute_diff_new_key():
    """Key present in merged but not in defaults is included in diff."""
    merged = {"a": 1, "b": 2}
    defaults = {"a": 1}
    diff = _compute_diff(merged, defaults)
    assert diff == {"b": 2}


def test_compute_diff_changed_value():
    """Key with different value from default is included in diff."""
    merged = {"a": 1, "b": "changed"}
    defaults = {"a": 1, "b": "original"}
    diff = _compute_diff(merged, defaults)
    assert diff == {"b": "changed"}


def test_compute_diff_nested_no_diff():
    """Identical nested dicts produce empty diff."""
    merged = {"nested": {"x": 1}}
    defaults = {"nested": {"x": 1}}
    assert _compute_diff(merged, defaults) == {}


def test_compute_diff_nested_with_diff():
    """Nested dicts: only diverging sub-keys are returned."""
    merged = {"nested": {"x": 1, "y": 99}}
    defaults = {"nested": {"x": 1, "y": 2}}
    diff = _compute_diff(merged, defaults)
    assert diff == {"nested": {"y": 99}}


def test_compute_diff_nested_new_key():
    """Nested dict with entirely new key."""
    merged = {"nested": {"x": 1, "new": "val"}}
    defaults = {"nested": {"x": 1}}
    diff = _compute_diff(merged, defaults)
    assert diff == {"nested": {"new": "val"}}


# ===========================================================================
# Tests for initialization
# ===========================================================================

def test_module_init_success(monkeypatch):
    """Test ModuleAdminConfig can be instantiated with valid mocked settings."""
    module, fake_db = _make_module(monkeypatch)
    assert isinstance(module, ModuleAdminConfig)
    assert module.sogo_db_manager is fake_db


def test_module_init_without_args_raises():
    """Test ModuleAdminConfig initialization without arguments raises TypeError."""
    with pytest.raises(TypeError):
        ModuleAdminConfig()


# ===========================================================================
# Tests for get_system_settings
# ===========================================================================

def test_get_system_settings_empty_table(monkeypatch):
    """get_system_settings returns empty dict when TABLE_SETTINGS is empty."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = []

    result = module.get_system_settings()

    assert result == {}


def test_get_system_settings_with_data(monkeypatch):
    """get_system_settings returns the stored settings dict."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(SYSTEM_SETTINGS,)]

    result = module.get_system_settings()

    assert result == SYSTEM_SETTINGS


def test_get_system_settings_too_many_rows_raises(monkeypatch):
    """get_system_settings raises AggravatedException when TABLE_SETTINGS has more than 1 row."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(SYSTEM_SETTINGS,), (SYSTEM_SETTINGS,)]

    with pytest.raises(AggravatedException):
        module.get_system_settings()


# ===========================================================================
# Tests for get_default_domain_settings
# ===========================================================================

def test_get_default_domain_settings_empty_table(monkeypatch):
    """get_default_domain_settings returns empty dict when table is empty."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = []

    result = module.get_default_domain_settings()

    assert result == {}


def test_get_default_domain_settings_with_data(monkeypatch):
    """get_default_domain_settings returns stored default domain settings."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(DEFAULT_DOMAIN_SETTINGS,)]

    result = module.get_default_domain_settings()

    assert result == DEFAULT_DOMAIN_SETTINGS


def test_get_default_domain_settings_too_many_rows_raises(monkeypatch):
    """get_default_domain_settings raises AggravatedException when table has more than 1 row."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(DEFAULT_DOMAIN_SETTINGS,), (DEFAULT_DOMAIN_SETTINGS,)]

    with pytest.raises(AggravatedException):
        module.get_default_domain_settings()


# ===========================================================================
# Tests for get_both_system_and_default_domain_settings
# ===========================================================================

def test_get_both_settings_returns_tuple(monkeypatch):
    """get_both_system_and_default_domain_settings returns a tuple of two dicts."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(SYSTEM_SETTINGS, DEFAULT_DOMAIN_SETTINGS)]

    result = module.get_both_system_and_default_domain_settings()

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] == SYSTEM_SETTINGS
    assert result[1] == DEFAULT_DOMAIN_SETTINGS


def test_get_both_settings_empty_table(monkeypatch):
    """get_both_system_and_default_domain_settings returns ({}, {}) when table is empty."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = []

    result = module.get_both_system_and_default_domain_settings()

    assert result == ({}, {})


# ===========================================================================
# Tests for get_one_domain_setting_diff
# ===========================================================================

def test_get_one_domain_setting_diff_no_domain(monkeypatch):
    """get_one_domain_setting_diff returns {} when domain not found."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = []

    result = module.get_one_domain_setting_diff(DOMAIN_ID)

    assert result == {}


def test_get_one_domain_setting_diff_with_data(monkeypatch):
    """get_one_domain_setting_diff returns the stored diff dict."""
    module, fake_db = _make_module(monkeypatch)
    diff = {"SOGoTimeZone": "Europe/Paris"}
    fake_db.select_result = [(diff,)]

    result = module.get_one_domain_setting_diff(DOMAIN_ID)

    assert result == diff


def test_get_one_domain_setting_diff_none_value(monkeypatch):
    """get_one_domain_setting_diff returns {} when stored value is None."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(None,)]

    result = module.get_one_domain_setting_diff(DOMAIN_ID)

    assert result == {}


# ===========================================================================
# Tests for get_one_domain_setting
# ===========================================================================

def test_get_one_domain_setting_not_found_returns_default(monkeypatch):
    """get_one_domain_setting returns default settings when domain does not exist."""
    module, fake_db = _make_module(monkeypatch)

    # First call (domain lookup) returns nothing; second call (default settings) returns data
    call_count = [0]
    def select_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return iter([])
        # second call is for default domain settings
        return iter([(DEFAULT_DOMAIN_SETTINGS,)])

    fake_db.select_from_table = lambda **kw: select_side_effect(**kw)

    # Patch to intercept positional calls too
    original_select = fake_db.select_from_table

    # Use monkeypatch on the method
    results_queue = [[], [(DEFAULT_DOMAIN_SETTINGS,)]]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select

    result = module.get_one_domain_setting("nonexistent.com")

    assert "settings" in result
    assert result["domain_name"] == "default"


def test_get_one_domain_setting_found_merges_with_defaults(monkeypatch):
    """get_one_domain_setting merges domain diff with default settings."""
    module, fake_db = _make_module(monkeypatch)

    domain_diff = {"SOGoTimeZone": "Europe/Paris"}
    default_settings = deepcopy(DEFAULT_DOMAIN_SETTINGS)

    # Queue: 1st select = domain row, 2nd select = default settings row
    from app.config.db import tables as tbl

    results_queue = [
        # domain select returns one row with all columns (id, hash, name, desc, info, settings, origin)
        [(
            1,
            "hash123",
            DOMAIN_ID,
            "Example description",
            {},
            domain_diff,
            {},
        )],
        # default settings select
        [(default_settings,)],
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select

    result = module.get_one_domain_setting(DOMAIN_ID)

    assert "settings" in result
    assert result["settings"]["SOGoTimeZone"] == "Europe/Paris"
    assert "origin" in result


def test_get_one_domain_setting_too_many_rows_raises(monkeypatch):
    """get_one_domain_setting raises AggravatedException when multiple rows found."""
    module, fake_db = _make_module(monkeypatch)

    row = (1, "hash", DOMAIN_ID, "desc", {}, {}, {})
    fake_db.select_result = [row, row]  # two identical rows => error
    with pytest.raises(AggravatedException):
        module.get_one_domain_setting(DOMAIN_ID)


# ===========================================================================
# Tests for create_domain_settings
# ===========================================================================

def test_create_domain_settings_success(monkeypatch):
    """create_domain_settings inserts a new domain and returns its data."""
    module, fake_db = _make_module(monkeypatch)

    # Queue: domain existence check returns empty; default settings returns data
    results_queue = [
        [],                               # domain does not exist yet
        [(DEFAULT_DOMAIN_SETTINGS,)],     # default domain settings
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select

    new_param = {
        "domain_name": DOMAIN_ID,
        "domain_description": "A test domain",
        "domain_info": {},
        "settings": {},
    }

    # Patch check_data_for_sogo_schemas to avoid schema validation
    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value={}):
        error_code, result = module.create_domain_settings(new_param)

    assert len(fake_db.insert_calls) == 1
    assert result["domain_name"] == DOMAIN_ID
    assert result["domain_description"] == "A test domain"
    assert "hash" in result
    assert "settings" in result
    assert "origin" in result


def test_create_domain_settings_domain_already_exists_raises(monkeypatch):
    """create_domain_settings raises RequestException when domain name is already taken."""
    module, fake_db = _make_module(monkeypatch)

    # Domain already exists
    fake_db.select_result = [(DOMAIN_ID,)]

    new_param = {
        "domain_name": DOMAIN_ID,
        "domain_description": "desc",
    }

    with pytest.raises(RequestException) as exc_info:
        module.create_domain_settings(new_param)

    assert exc_info.value.error == err.ERROR_DOMAIN_NAME_TAKEN


def test_create_domain_settings_insert_fails_raises(monkeypatch):
    """create_domain_settings raises BugException when insert returns wrong count."""
    module, fake_db = _make_module(monkeypatch)

    results_queue = [
        [],
        [(DEFAULT_DOMAIN_SETTINGS,)],
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select
    fake_db.insert_result = 0  # simulate insert failure

    new_param = {
        "domain_name": DOMAIN_ID,
        "domain_description": "desc",
        "settings": {},
    }

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value={}):
        with pytest.raises(BugException):
            module.create_domain_settings(new_param)


# ===========================================================================
# Tests for update_one_domain_settings
# ===========================================================================

def test_update_one_domain_settings_success(monkeypatch):
    """update_one_domain_settings updates an existing domain and returns new data."""
    module, fake_db = _make_module(monkeypatch)

    domain_diff = {"SOGoTimeZone": "UTC"}
    default_settings = deepcopy(DEFAULT_DOMAIN_SETTINGS)

    # Queue for all select calls:
    # 1. connect() + domain lookup in update_one_domain_settings
    # 2. domain lookup in get_one_domain_setting (called inside)
    # 3. default settings lookup
    results_queue = [
        [(1, "hash123", DOMAIN_ID, "desc", {}, domain_diff, {})],
        [(default_settings,)],
        [(default_settings,)],
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select

    new_param = {"SOGoTimeZone": "America/New_York"}

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value={}):
        error_code, result = module.update_one_domain_settings(DOMAIN_ID, new_param)

    assert len(fake_db.update_calls) == 1
    assert result["domain_name"] == DOMAIN_ID
    assert "settings" in result
    assert "origin" in result


def test_update_one_domain_settings_update_fails_raises(monkeypatch):
    """update_one_domain_settings raises BugException when update returns wrong count."""
    module, fake_db = _make_module(monkeypatch)

    domain_diff = {}
    default_settings = deepcopy(DEFAULT_DOMAIN_SETTINGS)

    results_queue = [
        [(1, "hash123", DOMAIN_ID, "desc", {}, domain_diff, {})],
        [(default_settings,)],
        [(default_settings,)],
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select
    fake_db.update_result = 0  # simulate failure

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value={}):
        with pytest.raises(BugException):
            module.update_one_domain_settings(DOMAIN_ID, {})


# ===========================================================================
# Tests for delete_one_domain_setting
# ===========================================================================

def test_delete_one_domain_setting_success(monkeypatch):
    """delete_one_domain_setting deletes the domain and returns count."""
    module, fake_db = _make_module(monkeypatch)

    results_queue = [
        [(1, "hash123", DOMAIN_ID, "desc", {}, {}, {})],
        [(DEFAULT_DOMAIN_SETTINGS,)],
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select

    result = module.delete_one_domain_setting(DOMAIN_ID)

    assert result == 1
    assert len(fake_db.delete_calls) == 1


def test_delete_one_domain_setting_propagates_error(monkeypatch):
    """delete_one_domain_setting propagates exception from the db manager."""
    module, fake_db = _make_module(monkeypatch)

    results_queue = [
        [(1, "hash123", DOMAIN_ID, "desc", {}, {}, {})],
        [(DEFAULT_DOMAIN_SETTINGS,)],
    ]
    idx = [0]

    def queued_select(table_name, column_tuple, condition=None, **kwargs):
        res = results_queue[idx[0]] if idx[0] < len(results_queue) else []
        idx[0] += 1
        return iter(res)

    fake_db.select_from_table = queued_select
    fake_db.delete_result = Exception("DB error")

    with pytest.raises(Exception, match="DB error"):
        module.delete_one_domain_setting(DOMAIN_ID)


# ===========================================================================
# Tests for update_system_settings
# ===========================================================================

def test_update_system_settings_insert_first_time(monkeypatch):
    """update_system_settings inserts when TABLE_SETTINGS is empty."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = []  # no row yet

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value=SYSTEM_SETTINGS):
        error_code, result = module.update_system_settings(SYSTEM_SETTINGS)

    assert len(fake_db.insert_calls) == 1
    assert result == SYSTEM_SETTINGS


def test_update_system_settings_update_existing(monkeypatch):
    """update_system_settings updates when TABLE_SETTINGS already has a row."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(deepcopy(SYSTEM_SETTINGS),)]

    new_values = {"SOGoSMTPServer": "smtp2.example.com"}

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value={**SYSTEM_SETTINGS, **new_values}):
        error_code, result = module.update_system_settings(new_values)

    assert len(fake_db.update_calls) == 1


def test_update_system_settings_too_many_rows_raises(monkeypatch):
    """update_system_settings raises AggravatedException when TABLE_SETTINGS has >1 row."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(SYSTEM_SETTINGS,), (SYSTEM_SETTINGS,)]

    with pytest.raises(AggravatedException):
        module.update_system_settings({})


# ===========================================================================
# Tests for update_domain_default_settings
# ===========================================================================

def test_update_domain_default_settings_insert_first_time(monkeypatch):
    """update_domain_default_settings inserts when TABLE_SETTINGS is empty."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = []

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value=DEFAULT_DOMAIN_SETTINGS):
        error_code, result = module.update_domain_default_settings(DEFAULT_DOMAIN_SETTINGS)

    assert len(fake_db.insert_calls) == 1


def test_update_domain_default_settings_update_existing(monkeypatch):
    """update_domain_default_settings updates when TABLE_SETTINGS already has a row."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(deepcopy(DEFAULT_DOMAIN_SETTINGS),)]

    new_values = {"SOGoTimeZone": "America/New_York"}

    with patch("app.module.admin.ModuleAdminConfig.check_data_for_sogo_schemas", return_value={**DEFAULT_DOMAIN_SETTINGS, **new_values}):
        error_code, result = module.update_domain_default_settings(new_values)

    assert len(fake_db.update_calls) == 1


def test_update_domain_default_settings_too_many_rows_raises(monkeypatch):
    """update_domain_default_settings raises AggravatedException when TABLE_SETTINGS has >1 row."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.select_result = [(DEFAULT_DOMAIN_SETTINGS,), (DEFAULT_DOMAIN_SETTINGS,)]

    with pytest.raises(AggravatedException):
        module.update_domain_default_settings({})


# ===========================================================================
# Tests for get_all_domains_settings
# ===========================================================================

def test_get_all_domains_settings_empty(monkeypatch):
    """get_all_domains_settings returns (0, []) when there are no domains."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.count_result = 0
    fake_db.select_result = []

    count, domains = module.get_all_domains_settings(_make_collection_param())

    assert count == 0
    assert domains == []


def test_get_all_domains_settings_with_results(monkeypatch):
    """get_all_domains_settings returns paginated domain list."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.count_result = 2

    from app.config.db import tables as tbl
    col_names = [col.name for col in tbl.TABLE_DOMAIN.columns]

    # Build two fake rows matching the column order
    def make_row(domain_name):
        row = []
        for col in tbl.TABLE_DOMAIN.columns:
            if col.name == tbl.COL_DOMAIN_NAME.name:
                row.append(domain_name)
            elif col.name == tbl.COL_DOMAIN_SETTINGS.name:
                row.append({})
            else:
                row.append(None)
        return tuple(row)

    fake_db.select_result = [make_row("a.com"), make_row("b.com")]

    count, domains = module.get_all_domains_settings(_make_collection_param())

    assert count == 2
    assert len(domains) == 2
    assert any(d.get(tbl.COL_DOMAIN_NAME.name) == "a.com" for d in domains)


def test_get_all_domains_settings_pagination(monkeypatch):
    """get_all_domains_settings passes pagination parameters to the db."""
    module, fake_db = _make_module(monkeypatch)
    fake_db.count_result = 50
    fake_db.select_result = []

    # page=3, page_size=10 => offset=20, limit=10
    module.get_all_domains_settings(_make_collection_param(page=3, page_size=10))

    assert len(fake_db.count_calls) == 1
