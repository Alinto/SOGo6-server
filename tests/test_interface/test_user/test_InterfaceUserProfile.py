"""
Tests unitaires pour InterfaceUserProfile (Interface layer).
Ces tests utilisent des fake modules pour tester la logique de l'interface.
"""
from app.interface.user.InterfaceUserProfile import InterfaceUserProfile
from app.utils.exceptions import RequestException
from app.utils import errors as err


class FakeModuleUserProfile:
    """Fake ModuleUserProfile for testing InterfaceUserProfile."""
    def __init__(self, process_settings, user_domain):
        self.process_settings = process_settings
        self.user_domain = user_domain

        # Tracking
        self.list_accounts_args = None
        self.get_user_preferences_args = None

        # Results
        self.list_accounts_result = [
            {"id": 0, "email": "user@example.com", "type": "imap"},
            {"id": 1, "email": "alias@example.com", "type": "imap"}
        ]
        self.get_user_preferences_result = {
            "language": "en",
            "theme": "light",
            "timezone": "UTC"
        }

    def list_accounts(self, user):
        """List user accounts."""
        self.list_accounts_args = user
        return self.list_accounts_result

    def get_user_preferences(self, uid):
        """Get user preferences."""
        self.get_user_preferences_args = uid
        return self.get_user_preferences_result


class FakeUser:
    """Fake User for testing."""
    def __init__(self, uid, source_id="default"):
        self.uid = uid
        self.source_id = source_id


class FakeDomainSchema:
    """Fake DomainSchema for testing."""
    def __init__(self, subparent, is_needed_by_ui, is_user_source=False):
        self.subparent = subparent
        self.is_needed_by_ui = is_needed_by_ui
        self.is_user_source = is_user_source

    def __eq__(self, other):
        """Check if this is UserSourceSettings."""
        # Check if comparing with the UserSourceSettings class
        if hasattr(other, '__name__') and other.__name__ == 'UserSourceSettings':
            return self.is_user_source
        # Check if comparing with another FakeDomainSchema
        if isinstance(other, FakeDomainSchema):
            return (self.subparent == other.subparent and
                    self.is_needed_by_ui == other.is_needed_by_ui and
                    self.is_user_source == other.is_user_source)
        return False


def patch_modules_on_interface(monkeypatch, fake_module_user_profile, fake_domain_schemas):
    """Patch modules in InterfaceUserProfile."""
    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.ModuleUserProfile",
        lambda *args, **kwargs: fake_module_user_profile
    )
    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.get_all_domain_schemas",
        lambda: fake_domain_schemas
    )


# ========== Tests for get_user_profile ==========

def test_get_user_profile_success(monkeypatch):
    """Test getting user profile with all data."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_user = FakeUser("testuser@example.com")

    # Create fake domain schemas
    fake_schemas = [
        FakeDomainSchema("AUTH_SETTINGS", ["auth_method", "session_timeout"]),
        FakeDomainSchema("MAIL_SETTINGS", ["smtp_host", "imap_host"]),
    ]

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""

    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    user_domain = {
        "AUTH_SETTINGS": {
            "auth_method": "ldap",
            "session_timeout": 3600,
            "other_setting": "value"
        },
        "MAIL_SETTINGS": {
            "smtp_host": "smtp.example.com",
            "imap_host": "imap.example.com"
        }
    }

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain=user_domain,
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 200
    assert "data" in result
    assert result["data"]["mailboxes"] == fake_module.list_accounts_result
    assert result["data"]["prefs"] == fake_module.get_user_preferences_result
    assert "ui" in result["data"]
    assert result["data"]["ui"]["auth_method"] == "ldap"
    assert result["data"]["ui"]["session_timeout"] == 3600
    assert result["data"]["ui"]["smtp_host"] == "smtp.example.com"
    assert result["data"]["ui"]["imap_host"] == "imap.example.com"
    assert fake_module.list_accounts_args == fake_user
    assert fake_module.get_user_preferences_args == "testuser@example.com"


def test_get_user_profile_with_user_source_settings(monkeypatch):
    """Test getting user profile with UserSourceSettings."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_user = FakeUser("testuser@example.com", source_id="ldap_source")

    # Create fake domain schemas including UserSourceSettings
    fake_schemas = [
        FakeDomainSchema("AUTH_SETTINGS", ["auth_method"]),
        FakeDomainSchema("USER_SOURCE", ["ldap_server", "ldap_port"], is_user_source=True),
    ]

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""

    # Set the __name__ attribute on the class itself, not as a class attribute
    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    user_domain = {
        "AUTH_SETTINGS": {
            "auth_method": "ldap"
        },
        "USER_SOURCE": {
            "ldap_source": {
                "ldap_server": "ldap.example.com",
                "ldap_port": 389
            },
            "other_source": {
                "ldap_server": "other.example.com",
                "ldap_port": 636
            }
        }
    }

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain=user_domain,
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 200
    assert result["data"]["ui"]["auth_method"] == "ldap"
    # Should use the user's source_id
    assert result["data"]["ui"]["ldap_server"] == "ldap.example.com"
    assert result["data"]["ui"]["ldap_port"] == 389


def test_get_user_profile_list_accounts_exception(monkeypatch):
    """Test error handling when list_accounts fails."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_module.list_accounts = lambda user: (_ for _ in ()).throw(
        RequestException("Cannot list accounts", err.ERROR_VALIDATION_ERROR)
    )
    fake_user = FakeUser("testuser@example.com")

    fake_schemas = []

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain={},
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 400
    assert result["error_code"] == err.ERROR_VALIDATION_ERROR.c


def test_get_user_profile_get_preferences_exception(monkeypatch):
    """Test error handling when get_user_preferences fails."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_module.get_user_preferences = lambda uid: (_ for _ in ()).throw(
        RequestException("Cannot get preferences", err.ERROR_VALIDATION_ERROR)
    )
    fake_user = FakeUser("testuser@example.com")

    fake_schemas = []

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""

    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain={},
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 400
    assert result["error_code"] == err.ERROR_VALIDATION_ERROR.c


def test_get_user_profile_missing_ui_settings(monkeypatch):
    """Test getting user profile when some UI settings are missing."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_user = FakeUser("testuser@example.com")

    fake_schemas = [
        FakeDomainSchema("AUTH_SETTINGS", ["auth_method", "missing_setting"]),
    ]

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""

    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    user_domain = {
        "AUTH_SETTINGS": {
            "auth_method": "plain"
            # missing_setting is not present
        }
    }

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain=user_domain,
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 200
    assert result["data"]["ui"]["auth_method"] == "plain"
    assert result["data"]["ui"]["missing_setting"] is None


def test_get_user_profile_empty_domain_schemas(monkeypatch):
    """Test getting user profile when there are no domain schemas."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_user = FakeUser("testuser@example.com")

    fake_schemas = []

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""

    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain={},
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 200
    assert result["data"]["mailboxes"] == fake_module.list_accounts_result
    assert result["data"]["prefs"] == fake_module.get_user_preferences_result
    assert result["data"]["ui"] == {}


def test_get_user_profile_empty_mailboxes(monkeypatch):
    """Test getting user profile when user has no mailboxes."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_module.list_accounts_result = []
    fake_user = FakeUser("newuser@example.com")

    fake_schemas = []

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""
        pass

    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain={},
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 200
    assert result["data"]["mailboxes"] == []
    assert result["data"]["prefs"] == fake_module.get_user_preferences_result


def test_get_user_profile_complex_domain_structure(monkeypatch):
    """Test getting user profile with complex domain structure."""
    fake_module = FakeModuleUserProfile(None, None)
    fake_user = FakeUser("testuser@example.com")

    fake_schemas = [
        FakeDomainSchema("AUTH_SETTINGS", ["method", "timeout"]),
        FakeDomainSchema("MAIL_SETTINGS", ["host", "port", "ssl"]),
        FakeDomainSchema("UI_SETTINGS", ["theme", "language"]),
    ]

    # Mock UserSourceSettings class
    class FakeUserSourceSettings:
        """Fake UserSourceSettings class to satisfy the interface's expectation."""

    FakeUserSourceSettings.__name__ = 'UserSourceSettings'

    monkeypatch.setattr(
        "app.interface.user.InterfaceUserProfile.UserSourceSettings",
        FakeUserSourceSettings
    )

    patch_modules_on_interface(monkeypatch, fake_module, fake_schemas)

    user_domain = {
        "AUTH_SETTINGS": {
            "method": "oauth2",
            "timeout": 7200
        },
        "MAIL_SETTINGS": {
            "host": "mail.example.com",
            "port": 993,
            "ssl": True
        },
        "UI_SETTINGS": {
            "theme": "dark",
            "language": "fr"
        }
    }

    interface = InterfaceUserProfile(
        process_settings={"test": "config"},
        user_domain=user_domain,
        user=fake_user
    )

    result, status_code = interface.get_user_profile()

    assert status_code == 200
    ui_data = result["data"]["ui"]
    assert ui_data["method"] == "oauth2"
    assert ui_data["timeout"] == 7200
    assert ui_data["host"] == "mail.example.com"
    assert ui_data["port"] == 993
    assert ui_data["ssl"] is True
    assert ui_data["theme"] == "dark"
    assert ui_data["language"] == "fr"
