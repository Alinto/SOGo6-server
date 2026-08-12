"""
Tests unitaires pour InterfaceAuthUser (Interface layer).
Ces tests utilisent des fake modules pour tester la logique de l'interface.
"""
import pytest
from app.interface.auth.InterfaceAuthUser import InterfaceAuthUser
from app.utils.exceptions import RequestException, BugException
from app.utils import errors as err


class FakeModuleAuth:
    """Fake ModuleAuth for testing InterfaceAuthUser."""
    def __init__(self, process, system_settings, default_auth, default_us_source):
        self.process = process
        self.system_settings = system_settings
        self.default_auth = default_auth
        self.default_us_source = default_us_source

        # Tracking
        self.get_login_mech_args = None
        self.get_user_and_domain_user_sources_args = None
        self.generate_voucher_from_user_args = None
        self.logout_user_args = None

        # Results
        self.get_login_mech_result = {"mechanism": "plain", "redirect": None}
        self.get_user_and_domain_user_sources_result = (None, {})
        self.generate_voucher_from_user_result = {"voucher": "test-voucher-123", "expiry": "2026-02-13"}

    def get_login_mech(self, user_uid):
        """Get login mechanism for user."""
        self.get_login_mech_args = user_uid
        return self.get_login_mech_result

    def get_user_and_domain_user_sources(self, uid, password):
        """Get user object and domain user sources."""
        self.get_user_and_domain_user_sources_args = (uid, password)
        return self.get_user_and_domain_user_sources_result

    def generate_voucher_from_user(self, user):
        """Generate voucher for authenticated user."""
        self.generate_voucher_from_user_args = user
        return self.generate_voucher_from_user_result

    def logout_user(self, voucher_data):
        """Revoke the session associated with the given voucher."""
        self.logout_user_args = voucher_data


class FakeModuleUserSource:
    """Fake ModuleUserSource for testing."""
    def __init__(self, domain_user_sources):
        self.domain_user_sources = domain_user_sources

        # Tracking
        self.check_login_args = None
        self.get_contact_info_args = None

        # Results
        self.check_login_result = True
        self.get_contact_info_result = {
            "email": "user@example.com",
            "name": "Test User",
            "phone": "+33123456789"
        }

    def check_login(self, user):
        """Check if login is valid."""
        self.check_login_args = user
        return self.check_login_result

    def get_contact_info(self, uid):
        """Get contact info for user."""
        self.get_contact_info_args = uid
        return self.get_contact_info_result


class FakeModuleUserProfile:
    """Fake ModuleUserProfile for testing."""
    def __init__(self, process, default_domain):
        self.process = process
        self.default_domain = default_domain

        # Tracking
        self.is_user_profile_present_args = None
        self.create_user_profile_args = None
        self.update_user_folders_args = None

        # Results
        self.is_user_profile_present_result = False

    def is_user_profile_present(self, uid):
        """Check if user profile exists."""
        self.is_user_profile_present_args = uid
        return self.is_user_profile_present_result

    def create_user_profile(self, user):
        """Create user profile."""
        self.create_user_profile_args = user

    def update_user_folders(self, uid, calendar_key, addressbook_key):
        """Update user folders with calendar and addressbook keys."""
        self.update_user_folders_args = (uid, calendar_key, addressbook_key)

    def get_partial_user_preferences(self, uid, subparent):
        """Return fake general preferences carrying the user timezone."""
        return {"USER_GENERAL": {"SOGO_U_TIMEZONE": "Europe/Paris"}}


class FakeCalendarObject:
    """Fake calendar object returned by create_personal_calendar."""
    def __init__(self, key="fake-calendar-key"):
        self.key = key


class FakeModuleCalendar:
    """Fake ModuleCalendar for testing."""
    def __init__(self, *args, **kwargs):
        self.create_personal_calendar_args = None
        self.create_personal_calendar_timezone = None

    def create_personal_calendar(self, user_uid, name="Personal Calendar", tz="UTC"):
        """Create personal calendar."""
        self.create_personal_calendar_args = user_uid
        self.create_personal_calendar_timezone = tz
        return FakeCalendarObject()


class FakeAddressbookObject:
    """Fake addressbook object returned by create_personal_addressbook."""
    def __init__(self, key="fake-addressbook-key"):
        self.key = key


class FakeModuleContact:
    """Fake ModuleContact for testing."""
    def __init__(self, *args, **kwargs):
        self.create_personal_addressbook_args = None

    def create_personal_addressbook(self, user_uid, name="Personal contacts"):
        """Create personal address book."""
        self.create_personal_addressbook_args = user_uid
        return FakeAddressbookObject()


class FakeUser:
    """Fake User object for testing."""
    def __init__(self, uid, password):
        self.uid = uid
        self.password = password
        self.mail = uid
        self.source_id = "source1"


class FakeModuleMail:
    """Fake ModuleMail for testing."""
    def __init__(self, user, mail_settings, process):
        self.user = user
        self.mail_settings = mail_settings
        self.process = process
        self.create_special_folders_args = None

    def create_special_folders_if_not_exist(self, account_id):
        """Create special folders if they don't exist."""
        self.create_special_folders_args = account_id


def patch_modules_on_interface(monkeypatch, fake_module_auth, fake_module_user_profile, fake_module_user_source_class):
    """Patch modules in InterfaceAuthUser."""
    monkeypatch.setattr(
        "app.interface.auth.InterfaceAuthUser.ModuleAuth",
        lambda *args, **kwargs: fake_module_auth
    )
    monkeypatch.setattr(
        "app.interface.auth.InterfaceAuthUser.ModuleUserProfile",
        lambda *args, **kwargs: fake_module_user_profile
    )
    monkeypatch.setattr(
        "app.interface.auth.InterfaceAuthUser.ModuleUserSource",
        fake_module_user_source_class
    )
    monkeypatch.setattr(
        "app.interface.auth.InterfaceAuthUser.ModuleCalendar",
        FakeModuleCalendar
    )
    monkeypatch.setattr(
        "app.interface.auth.InterfaceAuthUser.ModuleContact",
        FakeModuleContact
    )
    monkeypatch.setattr(
        "app.interface.auth.InterfaceAuthUser.ModuleMail",
        FakeModuleMail
    )


# ========== Tests for get_login_mech ==========

def test_get_login_mech_success(monkeypatch):
    """Test getting login mechanism for a valid user."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    result, status_code = interface.get_login_mech(user_uid="testuser@example.com", redirect="/dashboard")

    assert status_code == 200
    assert result["data"]["mechanism"] == "plain"
    assert fake_auth.get_login_mech_args == "testuser@example.com"


def test_get_login_mech_request_exception(monkeypatch):
    """Test error handling when getting login mechanism fails."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_auth.get_login_mech = lambda x: (_ for _ in ()).throw(
        RequestException("Domain not found", err.ERROR_DOMAIN_NAME_NOT_FOUND)
    )
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    result, status_code = interface.get_login_mech(user_uid="unknown@example.com", redirect="/dashboard")

    assert status_code == 404
    assert result["error_code"] == err.ERROR_DOMAIN_NAME_NOT_FOUND.c


# ========== Tests for plain_login ==========

def test_plain_login_success(monkeypatch):
    """Test successful plain login."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_user = FakeUser("testuser@example.com", "secret123")
    fake_auth.get_user_and_domain_user_sources_result = (fake_user, {"source1": {}})

    fake_profile = FakeModuleUserProfile(None, None)
    fake_profile.is_user_profile_present_result = True  # User already exists

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    data = {"username": "testuser@example.com", "password": "secret123"}
    result, status_code = interface.plain_login(data)

    assert status_code == 200
    assert result["data"]["voucher"] == "test-voucher-123"
    assert fake_auth.get_user_and_domain_user_sources_args == ("testuser@example.com", "secret123")
    assert fake_us_instance.check_login_args == fake_user


def test_plain_login_failed_authentication(monkeypatch):
    """Test failed authentication."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_user = FakeUser("testuser@example.com", "wrong")
    fake_auth.get_user_and_domain_user_sources_result = (fake_user, {"source1": {}})

    fake_profile = FakeModuleUserProfile(None, None)

    fake_us_instance = FakeModuleUserSource({})
    fake_us_instance.check_login_result = False  # Login fails
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    data = {"username": "testuser@example.com", "password": "wrong"}
    _result, status_code = interface.plain_login(data)

    assert status_code == 401


def test_plain_login_create_user_profile(monkeypatch):
    """Test plain login creates user profile and personal calendar on first login."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_user = FakeUser("newuser@example.com", "secret123")
    fake_auth.get_user_and_domain_user_sources_result = (fake_user, {"source1": {}})

    fake_profile = FakeModuleUserProfile(None, None)
    fake_profile.is_user_profile_present_result = False  # New user

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}}
    )

    data = {"username": "newuser@example.com", "password": "secret123"}
    _result, status_code = interface.plain_login(data)

    assert status_code == 200
    assert fake_profile.create_user_profile_args is not None
    assert fake_profile.create_user_profile_args.uid == "newuser@example.com"
    assert interface._module_calendar.create_personal_calendar_args == "newuser@example.com"  # pylint: disable=protected-access
    # The user's preferred timezone is forwarded to the default calendar.
    assert interface._module_calendar.create_personal_calendar_timezone == "Europe/Paris"  # pylint: disable=protected-access
    # The personal address book is provisioned at first login alongside the calendar.
    assert interface._module_contact.create_personal_addressbook_args == "newuser@example.com"  # pylint: disable=protected-access


def test_plain_login_profile_creation_request_exception(monkeypatch):
    """Test error handling when user profile creation fails with RequestException."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_user = FakeUser("newuser@example.com", "secret123")
    fake_auth.get_user_and_domain_user_sources_result = (fake_user, {"source1": {}})

    fake_profile = FakeModuleUserProfile(None, None)
    fake_profile.is_user_profile_present_result = False
    fake_profile.create_user_profile = lambda *args: (_ for _ in ()).throw(
        RequestException("User profile creation failed", err.ERROR_USER_PROFILE_CREATION_FAILED)
    )

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}}
    )

    data = {"username": "newuser@example.com", "password": "secret123"}
    result, status_code = interface.plain_login(data)

    # RequestException should set the http_status
    assert status_code >= 500
    assert result["error_code"] == err.ERROR_USER_PROFILE_CREATION_FAILED.c


def test_plain_login_profile_creation_bug_exception(monkeypatch):
    """Test error handling when user profile creation fails with BugException."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_user = FakeUser("newuser@example.com", "secret123")
    fake_auth.get_user_and_domain_user_sources_result = (fake_user, {"source1": {}})

    fake_profile = FakeModuleUserProfile(None, None)
    fake_profile.is_user_profile_present_result = False
    fake_profile.create_user_profile = lambda *args: (_ for _ in ()).throw(
        BugException("Unexpected error", err.ERROR_BUG_UNKNOWN_ORDER)
    )

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}}
    )

    data = {"username": "newuser@example.com", "password": "secret123"}

    # BugException is not caught in plain_login, so it propagates
    with pytest.raises(BugException) as exc_info:
        interface.plain_login(data)

    assert exc_info.value.error == err.ERROR_BUG_UNKNOWN_ORDER


# ========== Tests for logout ==========

def test_logout_success(monkeypatch):
    """Test successful logout: delegates to module_auth and returns 200."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    result, status_code = interface.logout("fake-jwt-token")

    assert status_code == 200
    assert result["data"] is None
    assert fake_auth.logout_user_args == "fake-jwt-token"


def test_logout_empty_token(monkeypatch):
    """Test logout with an empty token still calls module_auth.logout_user."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    result, status_code = interface.logout("")

    assert status_code == 200
    assert fake_auth.logout_user_args == ""


def test_logout_request_exception_returns_error_response(monkeypatch):
    """Test that a RequestException from logout_user is caught and returns an error response."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_auth.logout_user = lambda voucher_data: (_ for _ in ()).throw(
        RequestException("Voucher has expired or cannot be read", err.ERROR_USER_CREDS_NOT_VALID)
    )
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    result, status_code = interface.logout("expired-jwt-token")

    assert status_code == err.ERROR_USER_CREDS_NOT_VALID.h
    assert result["error_code"] == err.ERROR_USER_CREDS_NOT_VALID.c


def test_logout_invalid_voucher_type_returns_error_response(monkeypatch):
    """Test that a RequestException for wrong voucher type is properly returned."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_auth.logout_user = lambda voucher_data: (_ for _ in ()).throw(
        RequestException("Wrong data type for voucher", err.ERROR_WRONG_AUTHORIZATION_TYPE)
    )
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}}
    )

    result, status_code = interface.logout(12345)  # wrong type

    assert status_code == err.ERROR_WRONG_AUTHORIZATION_TYPE.h
    assert result["error_code"] == err.ERROR_WRONG_AUTHORIZATION_TYPE.c
