"""
Tests unitaires pour InterfaceSystem (Interface layer).
Ces tests utilisent des fake objects pour tester la logique de l'interface.
"""
from app.interface.system.InterfaceSystem import InterfaceSystem


class FakeSystemSettingsObj:
    """Fake SystemSettingsObj for testing InterfaceSystem."""
    def __init__(self, settings):
        self.settings = settings
        # Default values
        self.SOGO_S_DIRECT_LOGIN = settings.get("SOGO_S_DIRECT_LOGIN", False)


class FakeAuthSettingsObj:
    """Fake AuthSettingsObj for testing InterfaceSystem."""
    def __init__(self, settings):
        self.settings = settings
        # Default values
        self.SOGO_D_PWD_RECOVERY = settings.get("SOGO_D_PWD_RECOVERY", False)


def patch_settings_objects(monkeypatch, fake_system_class, fake_auth_class):
    """Patch SystemSettingsObj and AuthSettingsObj in InterfaceSystem module."""
    monkeypatch.setattr(
        "app.interface.system.InterfaceSystem.SystemSettingsObj",
        fake_system_class
    )
    monkeypatch.setattr(
        "app.interface.system.InterfaceSystem.AuthSettingsObj",
        fake_auth_class
    )


# ========== Tests for get_ui_system_param ==========

def test_get_ui_system_param_direct_login_disabled(monkeypatch):
    """Test getting UI system parameters when SOGO_S_DIRECT_LOGIN is disabled."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj, FakeAuthSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": False
        }
    }
    default_domain = {
        "AUTH_SETTINGS": {
            "SOGO_D_PWD_RECOVERY": True
        }
    }

    interface = InterfaceSystem(system_settings=system_settings, default_domain=default_domain)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert result["data"]["system"]["SOGO_S_DIRECT_LOGIN"] is False
    # SOGO_D_PWD_RECOVERY should NOT be in the result when direct login is disabled
    assert "SOGO_D_PWD_RECOVERY" not in result["data"]["system"]


def test_get_ui_system_param_direct_login_enabled(monkeypatch):
    """Test getting UI system parameters when SOGO_S_DIRECT_LOGIN is enabled."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj, FakeAuthSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }
    default_domain = {
        "AUTH_SETTINGS": {
            "SOGO_D_PWD_RECOVERY": True
        }
    }

    interface = InterfaceSystem(system_settings=system_settings, default_domain=default_domain)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert result["data"]["system"]["SOGO_S_DIRECT_LOGIN"] is True
    # SOGO_D_PWD_RECOVERY should be in the result when direct login is enabled
    assert result["data"]["system"]["SOGO_D_PWD_RECOVERY"] is True


def test_get_ui_system_param_direct_login_enabled_pwd_recovery_disabled(monkeypatch):
    """Test getting UI system parameters when direct login is enabled but password recovery is disabled."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj, FakeAuthSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }
    default_domain = {
        "AUTH_SETTINGS": {
            "SOGO_D_PWD_RECOVERY": False
        }
    }

    interface = InterfaceSystem(system_settings=system_settings, default_domain=default_domain)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert result["data"]["system"]["SOGO_S_DIRECT_LOGIN"] is True
    assert result["data"]["system"]["SOGO_D_PWD_RECOVERY"] is False


def test_get_ui_system_param_response_structure(monkeypatch):
    """Test that the response structure is correct."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj, FakeAuthSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }
    default_domain = {
        "AUTH_SETTINGS": {
            "SOGO_D_PWD_RECOVERY": True
        }
    }

    interface = InterfaceSystem(system_settings=system_settings, default_domain=default_domain)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert "data" in result
    assert "system" in result["data"]
    assert isinstance(result["data"]["system"], dict)


# ========== Tests for __init__ ==========

def test_init_creates_system_and_auth_objects(monkeypatch):
    """Test that __init__ correctly creates SystemSettingsObj and AuthSettingsObj."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj, FakeAuthSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }
    default_domain = {
        "AUTH_SETTINGS": {
            "SOGO_D_PWD_RECOVERY": False
        }
    }

    interface = InterfaceSystem(system_settings=system_settings, default_domain=default_domain)

    assert hasattr(interface, "system")
    assert hasattr(interface, "auth_default")
    assert interface.system.SOGO_S_DIRECT_LOGIN is True
    assert interface.auth_default.SOGO_D_PWD_RECOVERY is False
