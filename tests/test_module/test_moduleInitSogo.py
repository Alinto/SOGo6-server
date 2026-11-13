"""
Unit tests for the database check and update of ModuleInitSogo
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from packaging.version import Version

from app.config.db.tables import ALL_TABLES, TABLE_USER
from app.module import ModuleInitSogo as module_init
from app.module.ModuleInitSogo import ModuleInitSogo
from app.utils.exceptions import AggravatedException

MISSING_COLUMN = TABLE_USER.columns[-1].name


class FakeDatabase:
    """Database shared by the fake clients, as all of them would see the same tables"""

    def __init__(self):
        self.tables = {table.name: {col.name: next(iter(col.data_type_check)) for col in table.columns}
                       for table in ALL_TABLES}
        self.created = []
        self.stored_version = "6.0.0"
        self.set_versions = []


class FakeClient:
    def __init__(self, database):
        self.database = database

    def get_table_info(self, table_name):
        return self.database.tables.get(table_name, {})

    def create_several_table(self, tables):
        self.database.created = tables

    def close(self):
        pass


class FakeConfigModule:
    def __init__(self, database):
        self.database = database

    def get_version(self):
        return self.database.stored_version

    def set_version(self, version):
        self.database.stored_version = version
        self.database.set_versions.append(version)

    def close(self):
        pass


@pytest.fixture
def database(monkeypatch):
    fake = FakeDatabase()
    monkeypatch.setattr(module_init, "get_sogo6_database", lambda _: FakeClient(fake))
    monkeypatch.setattr(module_init, "ModuleAdminConfig", lambda _: FakeConfigModule(fake))
    monkeypatch.setattr(module_init, "__version__", "6.1.2")
    return fake


@pytest.fixture
def updates(monkeypatch):
    """Declare the update 6.1, it adds the missing column"""
    monkeypatch.setattr("app.update.LIST_UPDATE_VERSIONS", [Version("6.1")])
    update = MagicMock()
    script = ModuleType("app.update.update_6_1")
    script.update = update
    monkeypatch.setitem(sys.modules, "app.update.update_6_1", script)
    return update


def test_first_init_creates_the_tables(database):
    database.tables = {}
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    assert database.created == ALL_TABLES
    assert init.first_init is True
    assert not init.errors
    assert not database.set_versions


def test_column_order_does_not_matter(database):
    database.stored_version = "6.1.2"
    info = database.tables[TABLE_USER.name]
    database.tables[TABLE_USER.name] = dict(reversed(list(info.items())))
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    assert not init.errors
    assert init.first_init is False


def test_correct_database_stores_a_newer_version(database):
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    assert database.set_versions == ["6.1.2"]
    assert not init.errors


@pytest.mark.parametrize("stored", ["6.1.2", "7.0.0"])
def test_correct_database_keeps_a_same_or_newer_stored_version(database, stored):
    database.stored_version = stored
    ModuleInitSogo(MagicMock()).check_sogo_database()
    assert not database.set_versions


def test_correct_database_not_configured_yet(database):
    """No settings row yet: get_version returns an empty dict and there is nothing to update"""
    database.stored_version = {}
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    assert not init.errors
    assert not database.set_versions


def test_wrong_database_without_stored_version(database, updates):
    del database.tables[TABLE_USER.name][MISSING_COLUMN]
    database.stored_version = {}
    with pytest.raises(AggravatedException, match="no version is stored"):
        ModuleInitSogo(MagicMock()).check_sogo_database()
    updates.assert_not_called()


def test_wrong_database_with_invalid_stored_version(database):
    del database.tables[TABLE_USER.name][MISSING_COLUMN]
    database.stored_version = "not a version"
    with pytest.raises(AggravatedException, match="is invalid"):
        ModuleInitSogo(MagicMock()).check_sogo_database()


@pytest.mark.parametrize("stored", ["6.1.2", "6.1.0", "7.0.0"])
def test_wrong_database_without_update_is_an_error(database, updates, stored):
    """Same version, no update since the stored version, and rollback which is not supported"""
    del database.tables[TABLE_USER.name][MISSING_COLUMN]
    database.stored_version = stored
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    assert len(init.errors) == 1
    assert MISSING_COLUMN in init.errors[0]
    updates.assert_not_called()
    assert not database.set_versions


def test_missing_table_runs_the_update(database, updates):
    info = database.tables.pop(TABLE_USER.name)
    updates.side_effect = lambda: database.tables.__setitem__(TABLE_USER.name, info)
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    updates.assert_called_once()
    assert not init.errors
    assert init.first_init is False
    assert database.set_versions == ["6.1", "6.1.2"]


def test_missing_column_runs_the_update(database, updates):
    info = database.tables[TABLE_USER.name]
    column_type = info.pop(MISSING_COLUMN)
    updates.side_effect = lambda: info.__setitem__(MISSING_COLUMN, column_type)
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    updates.assert_called_once()
    assert not init.errors
    assert database.stored_version == "6.1.2"


def test_update_not_fixing_the_database_is_an_error(database, updates):
    del database.tables[TABLE_USER.name][MISSING_COLUMN]
    init = ModuleInitSogo(MagicMock())
    init.check_sogo_database()
    updates.assert_called_once()
    assert len(init.errors) == 1
    assert database.set_versions == ["6.1"]


def test_failing_update_stops_everything(database, updates):
    del database.tables[TABLE_USER.name][MISSING_COLUMN]
    updates.side_effect = ValueError("boom")
    with pytest.raises(AggravatedException, match="version 6.1 failed: boom"):
        ModuleInitSogo(MagicMock()).check_sogo_database()
    assert not database.set_versions
