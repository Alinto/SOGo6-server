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

def patch_settings_objects(monkeypatch, fake_system_class,):
    """Patch SystemSettingsObj in InterfaceSystem module."""
    monkeypatch.setattr(
        "app.interface.system.InterfaceSystem.SystemSettingsObj",
        fake_system_class
    )

# ========== Tests for get_ui_system_param ==========

def test_get_ui_system_param_direct_login_disabled(monkeypatch):
    """Test getting UI system parameters when SOGO_S_DIRECT_LOGIN is disabled."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": False
        }
    }

    interface = InterfaceSystem(system_settings=system_settings)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert result["data"]["system"]["SOGO_S_DIRECT_LOGIN"] is False



def test_get_ui_system_param_direct_login_enabled(monkeypatch):
    """Test getting UI system parameters when SOGO_S_DIRECT_LOGIN is enabled."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }

    interface = InterfaceSystem(system_settings=system_settings)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert result["data"]["system"]["SOGO_S_DIRECT_LOGIN"] is True



def test_get_ui_system_param_direct_login_enabled_pwd_recovery_disabled(monkeypatch):
    """Test getting UI system parameters when direct login is enabled but password recovery is disabled."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }


    interface = InterfaceSystem(system_settings=system_settings)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert result["data"]["system"]["SOGO_S_DIRECT_LOGIN"] is True


def test_get_ui_system_param_response_structure(monkeypatch):
    """Test that the response structure is correct."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }

    interface = InterfaceSystem(system_settings=system_settings)
    result, status_code = interface.get_ui_system_param()

    assert status_code == 200
    assert "data" in result
    assert "system" in result["data"]
    assert isinstance(result["data"]["system"], dict)


# ========== Tests for __init__ ==========

def test_init_creates_system_objects(monkeypatch):
    """Test that __init__ correctly creates SystemSettingsObj."""
    patch_settings_objects(monkeypatch, FakeSystemSettingsObj)

    system_settings = {
        "SYSTEM_SETTINGS": {
            "SOGO_S_DIRECT_LOGIN": True
        }
    }

    interface = InterfaceSystem(system_settings=system_settings)

    assert hasattr(interface, "system")
    assert interface.system.SOGO_S_DIRECT_LOGIN is True
