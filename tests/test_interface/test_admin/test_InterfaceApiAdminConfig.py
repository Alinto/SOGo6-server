"""
Tests unitaires pour InterfaceApiAdminConfig (Interface layer).
Ces tests utilisent un fake ModuleAdminConfig pour tester la logique de l'interface.
"""
from marshmallow.exceptions import ValidationError

from app.interface.admin.InterfaceApiAdminConfig import InterfaceApiAdminConfig
from app.utils.exceptions import RequestException
from app.utils import errors as err
from app.utils.db.Condition import Order


class FakeModuleAdminConfig:
    """Fake ModuleAdminConfig for testing InterfaceApiAdminConfig."""
    def __init__(self, process_settings):
        self.process_settings = process_settings

        # Tracking
        self.get_dynamic_form_settings_called = False
        self.get_system_settings_called = False
        self.update_system_settings_args = None
        self.get_default_domain_settings_called = False
        self.update_domain_default_settings_args = None
        self.get_all_domains_settings_args = None
        self.create_domain_settings_args = None
        self.get_one_domain_setting_args = None
        self.update_one_domain_settings_args = None
        self.delete_one_domain_setting_args = None

        # Results
        self.get_dynamic_form_settings_result = {
            "fields": [
                {"name": "field1", "type": "text"},
                {"name": "field2", "type": "number"}
            ]
        }
        self.get_system_settings_result = {
            "setting1": "value1",
            "setting2": "value2"
        }
        self.update_system_settings_result = (
            {"updated": True},
            {"setting1": "new_value1", "setting2": "value2"}
        )
        self.get_default_domain_settings_result = {
            "default_setting1": "default_value1",
            "default_setting2": "default_value2"
        }
        self.update_domain_default_settings_result = (
            {"updated": True},
            {"default_setting1": "new_default_value1"}
        )
        self.get_all_domains_settings_result = (
            2,
            [
                {"domain_id": "example.com", "domain_name": "Example"},
                {"domain_id": "test.com", "domain_name": "Test"}
            ]
        )
        self.create_domain_settings_result = (
            {"created": True},
            {"domain_id": "newdomain.com", "domain_name": "New Domain"}
        )
        self.get_one_domain_setting_result = {
            "domain_id": "example.com",
            "domain_name": "Example",
            "settings": {"key": "value"}
        }
        self.update_one_domain_settings_result = (
            {"updated": True},
            {"domain_id": "example.com", "domain_name": "Updated Example"}
        )
        self.delete_one_domain_setting_result = {"deleted": True}

    def get_dynamic_form_settings(self):
        """Get dynamic form settings."""
        self.get_dynamic_form_settings_called = True
        return self.get_dynamic_form_settings_result

    def get_system_settings(self):
        """Get system settings."""
        self.get_system_settings_called = True
        return self.get_system_settings_result

    def update_system_settings(self, new_param):
        """Update system settings."""
        self.update_system_settings_args = new_param
        return self.update_system_settings_result

    def get_default_domain_settings(self):
        """Get default domain settings."""
        self.get_default_domain_settings_called = True
        return self.get_default_domain_settings_result

    def update_domain_default_settings(self, new_param):
        """Update default domain settings."""
        self.update_domain_default_settings_args = new_param
        return self.update_domain_default_settings_result

    def get_all_domains_settings(self, offset, limit, columns=None, sort_by=None, order=None):
        """Get all domains settings."""
        self.get_all_domains_settings_args = (offset, limit, columns, sort_by, order)
        return self.get_all_domains_settings_result

    def create_domain_settings(self, new_domain):
        """Create domain settings."""
        self.create_domain_settings_args = new_domain
        return self.create_domain_settings_result

    def get_one_domain_setting(self, domain_id):
        """Get one domain setting."""
        self.get_one_domain_setting_args = domain_id
        return self.get_one_domain_setting_result

    def update_one_domain_settings(self, domain_id, new_data):
        """Update one domain settings."""
        self.update_one_domain_settings_args = (domain_id, new_data)
        return self.update_one_domain_settings_result

    def delete_one_domain_setting(self, domain_id):
        """Delete one domain setting."""
        self.delete_one_domain_setting_args = domain_id
        return self.delete_one_domain_setting_result


def patch_module_on_interface(monkeypatch, fake_module):
    """Patch ModuleAdminConfig in InterfaceApiAdminConfig module."""
    monkeypatch.setattr(
        "app.interface.admin.InterfaceApiAdminConfig.ModuleAdminConfig",
        lambda process_settings: fake_module
    )


# ========== Tests for get_dynamic_setting_structure ==========

def test_get_dynamic_setting_structure_success(monkeypatch):
    """Test getting dynamic setting structure."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result = interface.get_dynamic_setting_structure()

    assert result["data"]["fields"][0]["name"] == "field1"
    assert fake_module.get_dynamic_form_settings_called is True


# ========== Tests for get_all_setting_system ==========

def test_get_all_setting_system_success(monkeypatch):
    """Test getting all system settings."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result = interface.get_all_setting_system()

    assert result["data"]["setting1"] == "value1"
    assert result["data"]["setting2"] == "value2"
    assert fake_module.get_system_settings_called is True


# ========== Tests for update_all_setting_system ==========

def test_update_all_setting_system_success(monkeypatch):
    """Test updating all system settings."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_param = {"setting1": "new_value1"}
    result, status_code = interface.update_all_setting_system(new_param)

    assert status_code == 200
    assert result["data"]["setting1"] == "new_value1"
    assert fake_module.update_system_settings_args == new_param


def test_update_all_setting_system_validation_error(monkeypatch):
    """Test validation error when updating system settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.update_system_settings = lambda x: (_ for _ in ()).throw(
        ValidationError({"field": ["Invalid value"]})
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_param = {"setting1": "invalid"}
    result, status_code = interface.update_all_setting_system(new_param)

    assert status_code == 400
    assert result["error_code"] == err.ERROR_VALIDATION_ERROR.c


# ========== Tests for get_all_setting_domain_default ==========

def test_get_all_setting_domain_default_success(monkeypatch):
    """Test getting all default domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result = interface.get_all_setting_domain_default()

    assert result["data"]["default_setting1"] == "default_value1"
    assert fake_module.get_default_domain_settings_called is True


# ========== Tests for update_all_setting_domain_default ==========

def test_update_all_setting_domain_default_success(monkeypatch):
    """Test updating all default domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_param = {"default_setting1": "new_default_value1"}
    result, status_code = interface.update_all_setting_domain_default(new_param)

    assert status_code == 200
    assert result["data"]["default_setting1"] == "new_default_value1"
    assert fake_module.update_domain_default_settings_args == new_param


def test_update_all_setting_domain_default_validation_error(monkeypatch):
    """Test validation error when updating default domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.update_domain_default_settings = lambda x: (_ for _ in ()).throw(
        ValidationError({"field": ["Invalid value"]})
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_param = {"default_setting1": "invalid"}
    result, status_code = interface.update_all_setting_domain_default(new_param)

    assert status_code == 400
    assert result["error_code"] == err.ERROR_VALIDATION_ERROR.c


# ========== Tests for get_all_domain_settings ==========

def test_get_all_domain_settings_success(monkeypatch):
    """Test getting all domain settings with pagination."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    count, result, status_code = interface.get_all_domain_settings(
        first_item=0, last_item=10,
        sort_args={"sort_by": "domain_name", "sort_order": "asc"},
    )

    assert status_code == 200
    assert count == 2
    assert len(result["data"]) == 2
    assert result["data"][0]["domain_id"] == "example.com"
    assert fake_module.get_all_domains_settings_args[0] == 0  # offset
    assert fake_module.get_all_domains_settings_args[1] == 11  # limit
    assert fake_module.get_all_domains_settings_args[4] == Order.ASC  # order


def test_get_all_domain_settings_invalid_order(monkeypatch):
    """Test error handling when order string is invalid."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    count, result, status_code = interface.get_all_domain_settings(
        first_item=0, last_item=10,
        sort_args={"sort_by": None, "sort_order": "invalid"},
    )

    assert status_code == 400
    assert count == 0
    assert result["error_code"] == err.ERROR_BUG_UNKNOWN_ORDER.c


def test_get_all_domain_settings_invalid_sort_column(monkeypatch):
    """Test error handling when sort column is invalid."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    # Mock the TABLE_DOMAIN to raise RequestException
    from app.config.db import tables as tbl
    original_get_column = tbl.TABLE_DOMAIN.get_column_from_name

    def mock_get_column(name):
        raise RequestException("Unknown column", err.ERROR_BUG_UNKNWON_COLUMN)

    monkeypatch.setattr(tbl.TABLE_DOMAIN, "get_column_from_name", mock_get_column)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    count, result, status_code = interface.get_all_domain_settings(
        first_item=0, last_item=10,
        sort_args={"sort_by": "invalid_column", "sort_order": "asc"},
    )

    assert status_code == 400
    assert count == 0
    assert result["error_code"] == err.ERROR_BUG_UNKNWON_COLUMN.c

    # Restore original
    monkeypatch.setattr(tbl.TABLE_DOMAIN, "get_column_from_name", original_get_column)


def test_get_all_domain_settings_no_sort_order(monkeypatch):
    """Test getting all domain settings without sort and order."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    count, _result, status_code = interface.get_all_domain_settings(
        first_item=5, last_item=15,
    )

    assert status_code == 200
    assert count == 2
    assert fake_module.get_all_domains_settings_args[0] == 5  # offset
    assert fake_module.get_all_domains_settings_args[1] == 11  # limit
    assert fake_module.get_all_domains_settings_args[3] is None  # sort_by
    assert fake_module.get_all_domains_settings_args[4] == Order.ASC  # order (default)


# ========== Tests for post_new_domain_settings ==========

def test_post_new_domain_settings_success(monkeypatch):
    """Test creating new domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_domain = {
        "domain_name": "newdomain.com",
        "domain_description": "New Domain",
        "settings": {}
    }
    result, status_code = interface.post_new_domain_settings(new_domain)

    assert status_code == 200
    assert result["data"]["domain_id"] == "newdomain.com"
    assert fake_module.create_domain_settings_args == new_domain


def test_post_new_domain_settings_validation_error(monkeypatch):
    """Test validation error when creating new domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.create_domain_settings = lambda x: (_ for _ in ()).throw(
        ValidationError({"domain_name": ["Required field"]})
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_domain = {"settings": {}}
    result, status_code = interface.post_new_domain_settings(new_domain)

    assert status_code == 400
    assert result["error_code"] == err.ERROR_VALIDATION_ERROR.c


def test_post_new_domain_settings_request_exception(monkeypatch):
    """Test request exception when creating new domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.create_domain_settings = lambda x: (_ for _ in ()).throw(
        RequestException("Domain name taken", err.ERROR_DOMAIN_NAME_TAKEN)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_domain = {"domain_name": "existing.com"}
    result, status_code = interface.post_new_domain_settings(new_domain)

    assert status_code == 400
    assert result["error_code"] == err.ERROR_DOMAIN_NAME_TAKEN.c


# ========== Tests for get_domain_settings ==========

def test_get_domain_settings_success(monkeypatch):
    """Test getting domain settings for a specific domain."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result, status_code = interface.get_domain_settings(domain_id="example.com")

    assert status_code == 200
    assert result["data"]["domain_id"] == "example.com"
    assert fake_module.get_one_domain_setting_args == "example.com"


def test_get_domain_settings_not_found(monkeypatch):
    """Test error when domain settings not found."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.get_one_domain_setting = lambda x: (_ for _ in ()).throw(
        RequestException("Domain not found", err.ERROR_DOMAIN_NAME_NOT_FOUND)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result, status_code = interface.get_domain_settings(domain_id="nonexistent.com")

    assert status_code == 404
    assert result["error_code"] == err.ERROR_DOMAIN_NAME_NOT_FOUND.c


# ========== Tests for update_domain_settings ==========

def test_update_domain_settings_success(monkeypatch):
    """Test updating domain settings for a specific domain."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    new_data = {"domain_name": "Updated Example"}
    result, status_code = interface.update_domain_settings(
        domain_id="example.com", new_data=new_data
    )

    assert status_code == 200
    assert result["data"]["domain_name"] == "Updated Example"
    assert fake_module.update_one_domain_settings_args == ("example.com", new_data)


def test_update_domain_settings_not_found(monkeypatch):
    """Test error when updating non-existent domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.update_one_domain_settings = lambda x, y: (_ for _ in ()).throw(
        RequestException("Domain not found", err.ERROR_DOMAIN_NAME_NOT_FOUND)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result, status_code = interface.update_domain_settings(
        domain_id="nonexistent.com", new_data={}
    )

    assert status_code == 404
    assert result["error_code"] == err.ERROR_DOMAIN_NAME_NOT_FOUND.c


def test_update_domain_settings_validation_error(monkeypatch):
    """Test validation error when updating domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.update_one_domain_settings = lambda x, y: (_ for _ in ()).throw(
        ValidationError({"field": ["Invalid value"]})
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result, status_code = interface.update_domain_settings(
        domain_id="example.com", new_data={"invalid": "data"}
    )

    assert status_code == 400
    assert result["error_code"] == err.ERROR_VALIDATION_ERROR.c


# ========== Tests for delete_domain_settings ==========

def test_delete_domain_settings_success(monkeypatch):
    """Test deleting domain settings for a specific domain."""
    fake_module = FakeModuleAdminConfig(None)
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result, status_code = interface.delete_domain_settings(domain_id="example.com")

    assert status_code == 200
    assert not result
    assert fake_module.delete_one_domain_setting_args == "example.com"


def test_delete_domain_settings_not_found(monkeypatch):
    """Test error when deleting non-existent domain settings."""
    fake_module = FakeModuleAdminConfig(None)
    fake_module.delete_one_domain_setting = lambda x: (_ for _ in ()).throw(
        RequestException("Domain not found", err.ERROR_DOMAIN_NAME_NOT_FOUND)
    )
    patch_module_on_interface(monkeypatch, fake_module)

    process_setting = {"test": "config"}
    interface = InterfaceApiAdminConfig(process_setting=process_setting)

    result, status_code = interface.delete_domain_settings(domain_id="nonexistent.com")

    assert status_code == 404
    assert result["error_code"] == err.ERROR_DOMAIN_NAME_NOT_FOUND.c
