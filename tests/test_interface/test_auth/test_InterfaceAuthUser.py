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
        self.get_user_profile_args = None

        # Results
        self.is_user_profile_present_result = False
        self.folders = None  # Folders of the stored profile, None without profile

    def is_user_profile_present(self, uid):
        """Check if user profile exists."""
        self.is_user_profile_present_args = uid
        return self.is_user_profile_present_result or self.folders is not None

    def create_user_profile(self, user):
        """Create user profile."""
        self.create_user_profile_args = user
        self.folders = {}

    def update_user_folders(self, uid, calendar_key, addressbook_key):
        """Update user folders with calendar and addressbook keys."""
        self.update_user_folders_args = (uid, calendar_key, addressbook_key)
        self.folders = {"CALENDAR": calendar_key, "ADDRESSBOOKS": addressbook_key}

    def get_partial_user_preferences(self, uid, subparent):
        """Return fake general preferences carrying the user timezone."""
        return {"USER_GENERAL": {"SOGO_U_TIMEZONE": "Europe/Paris"}}

    def get_user_profile(self, user):
        """Fill the user with its profile."""
        self.get_user_profile_args = user
        if self.folders is None:
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)
        user.folders = self.folders


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
    def __init__(self, uid, password, authenticated=False):
        self.uid = uid
        self.password = password
        self.mail = uid
        self.source_id = "source1"
        self.authenticated = authenticated
        self.folders = {}


ANONYMOUS_USER = FakeUser("anonymous", "anonymous", authenticated=False)
ONBOARDED_FOLDERS = {"CALENDAR": "calendar-key", "ADDRESSBOOKS": "addressbook-key"}


class FakeCache:
    """Fake cache client keeping the onboarding lock."""
    def __init__(self):
        self.keys = {}
        self.reads = []

    def get(self, key, expected_type):
        """Return the value of a key, None if absent."""
        self.reads.append(key)
        return self.keys.get(key)

    def set(self, key, value, ttl, nx=False):
        """Store a value, or refuse it with nx when the key is held."""
        if nx and key in self.keys:
            return False
        self.keys[key] = value
        return True

    def delete(self, *keys):
        """Delete keys."""
        for key in keys:
            self.keys.pop(key, None)


class FakeModuleMail:
    """Fake ModuleMail for testing."""
    def __init__(self, user, mail_settings, process_setting):
        self.user = user
        self.mail_settings = mail_settings
        self.process = process_setting
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
    fake_cache = FakeCache()
    monkeypatch.setattr("app.interface.auth.InterfaceAuthUser.sogo_cache", lambda: fake_cache)
    return fake_cache


# ========== Tests for get_login_mech ==========

def test_get_login_mech_success(monkeypatch):
    """Test getting login mechanism for a valid user."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
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
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
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
    fake_profile.folders = ONBOARDED_FOLDERS

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    fake_cache = patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
    )

    data = {"username": "testuser@example.com", "password": "secret123"}
    result, status_code = interface.plain_login(data)

    assert status_code == 200
    assert result["data"]["voucher"] == "test-voucher-123"
    assert fake_auth.get_user_and_domain_user_sources_args == ("testuser@example.com", "secret123")
    assert fake_us_instance.check_login_args == fake_user
    # The profile of an onboarded user is read without looking at the onboarding lock
    assert not fake_cache.reads


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
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
    )

    data = {"username": "testuser@example.com", "password": "wrong"}
    _result, status_code = interface.plain_login(data)

    assert status_code == 401


def test_plain_login_already_logged_in_same_user(monkeypatch):
    """Test that a login request from an already authenticated user for the same uid is short-circuited."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_profile = FakeModuleUserProfile(None, None)

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    logged_user = FakeUser("testuser@example.com", "secret123", authenticated=True)
    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=logged_user
    )

    data = {"username": "testuser@example.com", "password": "secret123"}
    result, status_code = interface.plain_login(data, "current-jwt-token")

    assert status_code == 200
    assert result["error_code"] == err.ERROR_NO_ERROR.c
    # The current token is returned as is
    assert result["data"] == {"jwt_token": "current-jwt-token"}
    # No new session should have been created
    assert fake_auth.get_user_and_domain_user_sources_args is None


def test_plain_login_already_logged_in_different_user_proceeds(monkeypatch):
    """Test that an authenticated user trying to login as someone else goes through the normal flow."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_user = FakeUser("otheruser@example.com", "secret123")
    fake_auth.get_user_and_domain_user_sources_result = (fake_user, {"source1": {}})

    fake_profile = FakeModuleUserProfile(None, None)
    fake_profile.is_user_profile_present_result = True  # User already exists
    fake_profile.folders = ONBOARDED_FOLDERS

    fake_us_instance = FakeModuleUserSource({})
    def fake_us_class(sources):
        return fake_us_instance

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    logged_user = FakeUser("testuser@example.com", "secret123", authenticated=True)
    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=logged_user
    )

    data = {"username": "otheruser@example.com", "password": "secret123"}
    result, status_code = interface.plain_login(data)

    assert status_code == 200
    assert result["data"]["voucher"] == "test-voucher-123"
    assert fake_auth.get_user_and_domain_user_sources_args == ("otheruser@example.com", "secret123")


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

    fake_cache = patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}},
        user=ANONYMOUS_USER
    )

    data = {"username": "newuser@example.com", "password": "secret123"}
    _result, status_code = interface.plain_login(data)

    assert status_code == 200
    # The onboarding lock is released
    assert not fake_cache.keys
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

    fake_cache = patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, fake_us_class)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}},
        user=ANONYMOUS_USER
    )

    data = {"username": "newuser@example.com", "password": "secret123"}
    result, status_code = interface.plain_login(data)

    # RequestException should set the http_status
    assert status_code >= 500
    assert result["error_code"] == err.ERROR_USER_PROFILE_CREATION_FAILED.c
    # The onboarding lock is released for the next request to retry
    assert not fake_cache.keys
    # No session is created for a user whose onboarding failed
    assert fake_auth.generate_voucher_from_user_args is None


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
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}},
        user=ANONYMOUS_USER
    )

    data = {"username": "newuser@example.com", "password": "secret123"}

    # BugException is not caught in plain_login, so it propagates
    with pytest.raises(BugException) as exc_info:
        interface.plain_login(data)

    assert exc_info.value.error == err.ERROR_BUG_UNKNOWN_ORDER


# ========== Tests for the onboarding of a first sign-in ==========

def _onboarding_interface(monkeypatch, fake_profile):
    """Build the interface for a user who never signed in, with fake modules and cache."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_auth.get_user_and_domain_user_sources_result = (FakeUser("newuser@example.com", "secret123"), {"source1": {}})
    fake_cache = patch_modules_on_interface(
        monkeypatch, fake_auth, fake_profile, lambda sources: FakeModuleUserSource({})
    )
    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}, "MAIL_SETTINGS": {"test": "value"}},
        user=ANONYMOUS_USER
    )
    return interface, fake_cache


def test_onboarding_waits_for_other_request(monkeypatch):
    """A request arriving during the onboarding run by another one waits for it and creates nothing."""
    fake_profile = FakeModuleUserProfile(None, None)
    interface, fake_cache = _onboarding_interface(monkeypatch, fake_profile)
    fake_cache.keys["onboarding_lock:newuser@example.com"] = "other request"

    def other_request_ends(_seconds):
        fake_cache.keys.clear()
        fake_profile.folders = ONBOARDED_FOLDERS

    monkeypatch.setattr("app.interface.auth.InterfaceAuthUser.sleep", other_request_ends)

    _result, status_code = interface.plain_login({"username": "newuser@example.com", "password": "secret123"})

    assert status_code == 200
    assert fake_profile.create_user_profile_args is None


def test_onboarding_running_too_long(monkeypatch):
    """A request gives up when the onboarding of another one lasts more than the wait timeout."""
    fake_profile = FakeModuleUserProfile(None, None)
    interface, fake_cache = _onboarding_interface(monkeypatch, fake_profile)
    fake_cache.keys["onboarding_lock:newuser@example.com"] = "other request"
    clock = iter([0.0, 11.0])
    monkeypatch.setattr("app.interface.auth.InterfaceAuthUser.monotonic", lambda: next(clock))
    monkeypatch.setattr("app.interface.auth.InterfaceAuthUser.sleep", lambda _seconds: None)

    with pytest.raises(RequestException) as exc_info:
        interface.onboard_user_and_fill_info(FakeUser("newuser@example.com", "secret123"), fake_cache)

    assert exc_info.value.error == err.ERROR_LOGIN_ONBOARDING_RUNNING
    assert fake_profile.create_user_profile_args is None


def test_onboarding_lock_taken_meanwhile(monkeypatch):
    """A request losing the lock to another one, which onboards the user, creates nothing."""
    fake_profile = FakeModuleUserProfile(None, None)
    interface, fake_cache = _onboarding_interface(monkeypatch, fake_profile)

    def other_request_onboards(key, value, ttl, nx=False):
        fake_profile.folders = ONBOARDED_FOLDERS
        return False

    fake_cache.set = other_request_onboards

    _result, status_code = interface.plain_login({"username": "newuser@example.com", "password": "secret123"})

    assert status_code == 200
    assert fake_profile.create_user_profile_args is None


def test_onboarding_keeps_lock_of_other_request(monkeypatch):
    """A lock expired during the onboarding and taken by another request is left to that request."""
    fake_profile = FakeModuleUserProfile(None, None)
    interface, fake_cache = _onboarding_interface(monkeypatch, fake_profile)

    def lock_expired_and_taken(_user):
        fake_cache.keys["onboarding_lock:newuser@example.com"] = "other request"

    fake_profile.create_user_profile = lock_expired_and_taken

    interface.plain_login({"username": "newuser@example.com", "password": "secret123"})

    assert fake_cache.keys == {"onboarding_lock:newuser@example.com": "other request"}


def test_onboard_user_and_fill_info(monkeypatch):
    """A user who never signed in is onboarded before its profile is read."""
    fake_profile = FakeModuleUserProfile(None, None)
    interface, fake_cache = _onboarding_interface(monkeypatch, fake_profile)
    user = FakeUser("newuser@example.com", "secret123")

    interface.onboard_user_and_fill_info(user, fake_cache)

    assert fake_profile.create_user_profile_args is user
    assert user.folders == {"CALENDAR": "fake-calendar-key", "ADDRESSBOOKS": "fake-addressbook-key"}
    assert not fake_cache.keys


def test_fill_info_of_onboarded_user(monkeypatch):
    """The profile of an onboarded user is read without looking at the onboarding lock."""
    fake_profile = FakeModuleUserProfile(None, None)
    fake_profile.folders = ONBOARDED_FOLDERS
    interface, fake_cache = _onboarding_interface(monkeypatch, fake_profile)
    user = FakeUser("alice@example.com", "secret123")

    interface.onboard_user_and_fill_info(user, fake_cache)

    assert user.folders is fake_profile.folders
    assert not fake_cache.reads
    assert fake_profile.is_user_profile_present_args is None


# ========== Tests for logout ==========

def test_logout_success(monkeypatch):
    """Test successful logout: delegates to module_auth and returns 200."""
    fake_auth = FakeModuleAuth(None, None, None, None)
    fake_profile = FakeModuleUserProfile(None, None)

    patch_modules_on_interface(monkeypatch, fake_auth, fake_profile, FakeModuleUserSource)

    interface = InterfaceAuthUser(
        process={"test": "config"},
        system={"SYSTEM_SETTINGS": {"test": "value"}},
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
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
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
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
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
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
        default_domain={"AUTH_SETTINGS": {"test": "value"}, "USER_SOURCE": {}},
        user=ANONYMOUS_USER
    )

    result, status_code = interface.logout(12345)  # wrong type

    assert status_code == err.ERROR_WRONG_AUTHORIZATION_TYPE.h
    assert result["error_code"] == err.ERROR_WRONG_AUTHORIZATION_TYPE.c
