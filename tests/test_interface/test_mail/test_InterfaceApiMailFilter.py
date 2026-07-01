# pylint: disable=invalid-sequence-index
from app.interface.mail.InterfaceApiMailFilter import InterfaceApiMailFilter
from app.utils.exceptions import RequestException
from app.utils import errors as err
from app.utils.constants import (
    FILTER_SECTION_FILTERS,
    FILTER_SECTION_VACATION,
    FILTER_SECTION_FORWARD,
    FILTER_SECTION_NOTIFICATION,
)


class InterfaceApiMailFilterWithInjectedConf(InterfaceApiMailFilter):
    """Subclass of InterfaceApiMailFilter that allows injecting modules directly for testing."""

    def __init__(self, filter_module, user_module=None):
        """Initialize with injected modules for testing.

        Does not call the parent __init__ to avoid requiring all the parameters it needs.
        The filter_module and user_module are set directly so tests can inject fake/mock modules.
        """
        self.filter_module = filter_module
        self.user_module = user_module


class FakeModuleFilter:
    """
    Fake ModuleFilter for testing InterfaceApiMailFilter.
    All methods mirror the ModuleFilter public API (get_section / set_section).
    """

    def __init__(self):
        # --- Memorisation des args pour vérification ---
        self.get_section_args = None
        self.set_section_args = None

        # --- Résultats configurables par test ---
        self.get_section_result = None
        self.set_section_result = {}

    def get_section(self, section_key):
        """Read one section from the stored filters column."""
        self.get_section_args = section_key
        return self.get_section_result

    def set_section(self, section_key, value):
        """Replace one section of the stored filters column and push to Sieve."""
        self.set_section_args = (section_key, value)
        return self.set_section_result


class FakeModuleUserProfile:
    """
    Fake ModuleUserProfile for testing InterfaceApiMailFilter._get_user_timezone.
    """

    def __init__(self, timezone="Europe/Paris"):
        self.timezone = timezone
        self.get_partial_user_preferences_args = None

    def get_partial_user_preferences(self, uid, subparent):
        """Return a minimal user preferences dict with a timezone entry."""
        self.get_partial_user_preferences_args = (uid, subparent)
        return {"USER_GENERAL": {"SOGO_U_TIMEZONE": self.timezone}}


class FakeUser:
    """Minimal fake user carrying only the uid needed by _get_user_timezone."""
    uid = "testuser"


def make_interface(fake_filter_module, fake_user_module=None):
    """Create an InterfaceApiMailFilterWithInjectedConf with the given fake modules."""
    return InterfaceApiMailFilterWithInjectedConf(fake_filter_module, fake_user_module)


# ========== Tests for set_filters ==========

def test_set_filters_success():
    """Test setting the filters list successfully."""
    fake_module = FakeModuleFilter()
    filters = [{"enabled": 1, "name": "Rule1", "actions": [], "conditions": []}]
    fake_module.set_section_result = {FILTER_SECTION_FILTERS: filters}
    interface = make_interface(fake_module)

    result, status_code = interface.set_filters(filters)

    assert status_code == 200
    assert result["data"] == {FILTER_SECTION_FILTERS: filters}
    assert fake_module.set_section_args == (FILTER_SECTION_FILTERS, filters)


def test_set_filters_module_exception():
    """Test error handling when set_filters raises a RequestException (profile not found)."""
    fake_module = FakeModuleFilter()
    fake_module.set_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Profile not found", err.ERROR_USER_PROFILE_NOT_FOUND)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.set_filters([])

    assert result["error_code"] == "S000317"
    assert status_code == 404


def test_set_filters_sieve_exception():
    """Test error handling when set_filters raises a Sieve-related RequestException."""
    fake_module = FakeModuleFilter()
    fake_module.set_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Sieve connection failed", err.ERROR_SIEVE_CONNECTION_FAILED)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.set_filters([])

    assert result["error_code"] == "S001501"
    assert status_code >= 500


# ========== Tests for set_vacation ==========

def test_set_vacation_success_with_timezone():
    """Test setting vacation when a timezone is already provided — user_module must not be called."""
    fake_module = FakeModuleFilter()
    vacation_input = {"enabled": 1, "text": "I am on vacation", "timezone": "Europe/London"}
    fake_module.set_section_result = {FILTER_SECTION_VACATION: vacation_input}
    fake_user_module = FakeModuleUserProfile(timezone="Europe/Paris")
    interface = make_interface(fake_module, fake_user_module)

    result, status_code = interface.set_vacation(vacation_input)

    assert status_code == 200
    assert result["data"] == {FILTER_SECTION_VACATION: vacation_input}
    # Timezone already set — user_module must NOT have been queried
    assert fake_user_module.get_partial_user_preferences_args is None
    # The value forwarded to set_section must preserve the original timezone
    assert fake_module.set_section_args[1]["timezone"] == "Europe/London"


def test_set_vacation_success_without_timezone_injects_user_tz():
    """Test that the user's timezone is injected when vacation carries no timezone."""
    fake_module = FakeModuleFilter()
    vacation_input = {"enabled": 1, "text": "I am on vacation"}
    fake_module.set_section_result = {FILTER_SECTION_VACATION: vacation_input}
    fake_user_module = FakeModuleUserProfile(timezone="America/New_York")
    interface = make_interface(fake_module, fake_user_module)
    interface.user = FakeUser()

    result, status_code = interface.set_vacation(vacation_input)

    assert status_code == 200
    # The timezone injected into set_section must be the one from user preferences
    assert fake_module.set_section_args[1]["timezone"] == "America/New_York"
    # The original dict is mutated by set_vacation to include the timezone
    assert vacation_input["timezone"] == "America/New_York"


def test_set_vacation_without_timezone_defaults_to_utc_when_user_module_fails():
    """Test that UTC is used as fallback when user_module raises an exception."""
    fake_module = FakeModuleFilter()
    vacation_input = {"enabled": 1, "text": "I am on vacation"}
    fake_module.set_section_result = {FILTER_SECTION_VACATION: vacation_input}
    fake_user_module = FakeModuleUserProfile()
    fake_user_module.get_partial_user_preferences = lambda *args: (_ for _ in ()).throw(
        Exception("DB error")
    )
    interface = make_interface(fake_module, fake_user_module)
    interface.user = FakeUser()

    result, status_code = interface.set_vacation(vacation_input)

    assert status_code == 200
    assert fake_module.set_section_args[1]["timezone"] == "UTC"


def test_set_vacation_module_exception():
    """Test error handling when set_vacation raises a RequestException (update failed)."""
    fake_module = FakeModuleFilter()
    fake_module.set_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Update failed", err.ERROR_USER_PROFILE_UPDATE_FAILED)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.set_vacation({"enabled": 1, "text": "Away", "timezone": "UTC"})

    assert result["error_code"] == "S000318"
    assert status_code >= 500


# ========== Tests for set_forward ==========

def test_set_forward_success():
    """Test setting forward settings successfully."""
    fake_module = FakeModuleFilter()
    forward_input = {"enabled": 1, "forwardAddress": "other@example.com"}
    fake_module.set_section_result = {FILTER_SECTION_FORWARD: forward_input}
    interface = make_interface(fake_module)

    result, status_code = interface.set_forward(forward_input)

    assert status_code == 200
    assert result["data"] == {FILTER_SECTION_FORWARD: forward_input}
    assert fake_module.set_section_args == (FILTER_SECTION_FORWARD, forward_input)


def test_set_forward_module_exception():
    """Test error handling when set_forward raises a RequestException (profile not found)."""
    fake_module = FakeModuleFilter()
    fake_module.set_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Profile not found", err.ERROR_USER_PROFILE_NOT_FOUND)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.set_forward({"enabled": 1, "forwardAddress": "x@x.com"})

    assert result["error_code"] == "S000317"
    assert status_code == 404


def test_set_forward_sieve_exception():
    """Test error handling when set_forward raises a Sieve push RequestException."""
    fake_module = FakeModuleFilter()
    fake_module.set_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Sieve push failed", err.ERROR_SIEVE_PUSH_FAILED)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.set_forward({"enabled": 1, "forwardAddress": "x@x.com"})

    assert result["error_code"] == "S001508"
    assert status_code >= 500


# ========== Tests for set_notification ==========

def test_set_notification_success():
    """Test setting notification settings successfully."""
    fake_module = FakeModuleFilter()
    notification_input = {"enabled": 1, "method": "mailto:admin@example.com"}
    fake_module.set_section_result = {FILTER_SECTION_NOTIFICATION: notification_input}
    interface = make_interface(fake_module)

    result, status_code = interface.set_notification(notification_input)

    assert status_code == 200
    assert result["data"] == {FILTER_SECTION_NOTIFICATION: notification_input}
    assert fake_module.set_section_args == (FILTER_SECTION_NOTIFICATION, notification_input)


def test_set_notification_module_exception():
    """Test error handling when set_notification raises a Sieve RequestException."""
    fake_module = FakeModuleFilter()
    fake_module.set_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Sieve push failed", err.ERROR_SIEVE_PUSH_FAILED)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.set_notification({"enabled": 1, "method": "mailto:x@x.com"})

    assert result["error_code"] == "S001508"
    assert status_code >= 500


# ========== Tests for get_filters ==========

def test_get_filters_success():
    """Test fetching the filters list successfully."""
    fake_module = FakeModuleFilter()
    filters_value = [{"enabled": 1, "name": "Rule1", "actions": [], "conditions": []}]
    fake_module.get_section_result = filters_value
    interface = make_interface(fake_module)

    result, status_code = interface.get_filters()

    assert status_code == 200
    assert result["data"] == {"filters": filters_value}
    assert fake_module.get_section_args == FILTER_SECTION_FILTERS


def test_get_filters_returns_none_when_not_set():
    """Test that get_filters wraps None correctly when no filters are stored."""
    fake_module = FakeModuleFilter()
    fake_module.get_section_result = None
    interface = make_interface(fake_module)

    result, status_code = interface.get_filters()

    assert status_code == 200
    assert result["data"] == {"filters": None}


def test_get_filters_module_exception():
    """Test error handling when get_filters raises a RequestException (profile not found)."""
    fake_module = FakeModuleFilter()
    fake_module.get_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Profile not found", err.ERROR_USER_PROFILE_NOT_FOUND)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.get_filters()

    assert result["error_code"] == "S000317"
    assert status_code == 404


# ========== Tests for get_vacation ==========

def test_get_vacation_success():
    """Test fetching vacation settings successfully."""
    fake_module = FakeModuleFilter()
    vacation_value = {"enabled": 1, "text": "I am on vacation", "timezone": "Europe/Paris"}
    fake_module.get_section_result = vacation_value
    interface = make_interface(fake_module)

    result, status_code = interface.get_vacation()

    assert status_code == 200
    assert result["data"] == {"vacation": vacation_value}
    assert fake_module.get_section_args == FILTER_SECTION_VACATION


def test_get_vacation_returns_none_when_not_set():
    """Test that get_vacation wraps None correctly when no vacation is configured."""
    fake_module = FakeModuleFilter()
    fake_module.get_section_result = None
    interface = make_interface(fake_module)

    result, status_code = interface.get_vacation()

    assert status_code == 200
    assert result["data"] == {"vacation": None}


def test_get_vacation_module_exception():
    """Test error handling when get_vacation raises a RequestException (profile not found)."""
    fake_module = FakeModuleFilter()
    fake_module.get_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Profile not found", err.ERROR_USER_PROFILE_NOT_FOUND)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.get_vacation()

    assert result["error_code"] == "S000317"
    assert status_code == 404


# ========== Tests for get_forward ==========

def test_get_forward_success():
    """Test fetching forward settings successfully."""
    fake_module = FakeModuleFilter()
    forward_value = {"enabled": 1, "forwardAddress": "other@example.com"}
    fake_module.get_section_result = forward_value
    interface = make_interface(fake_module)

    result, status_code = interface.get_forward()

    assert status_code == 200
    assert result["data"] == {"forward": forward_value}
    assert fake_module.get_section_args == FILTER_SECTION_FORWARD


def test_get_forward_returns_none_when_not_set():
    """Test that get_forward wraps None correctly when no forward is configured."""
    fake_module = FakeModuleFilter()
    fake_module.get_section_result = None
    interface = make_interface(fake_module)

    result, status_code = interface.get_forward()

    assert status_code == 200
    assert result["data"] == {"forward": None}


def test_get_forward_module_exception():
    """Test error handling when get_forward raises a RequestException (profile not found)."""
    fake_module = FakeModuleFilter()
    fake_module.get_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Profile not found", err.ERROR_USER_PROFILE_NOT_FOUND)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.get_forward()

    assert result["error_code"] == "S000317"
    assert status_code == 404


# ========== Tests for get_notification ==========

def test_get_notification_success():
    """Test fetching notification settings successfully."""
    fake_module = FakeModuleFilter()
    notification_value = {"enabled": 1, "method": "mailto:admin@example.com"}
    fake_module.get_section_result = notification_value
    interface = make_interface(fake_module)

    result, status_code = interface.get_notification()

    assert status_code == 200
    assert result["data"] == {"notification": notification_value}
    assert fake_module.get_section_args == FILTER_SECTION_NOTIFICATION


def test_get_notification_returns_none_when_not_set():
    """Test that get_notification wraps None correctly when no notification is configured."""
    fake_module = FakeModuleFilter()
    fake_module.get_section_result = None
    interface = make_interface(fake_module)

    result, status_code = interface.get_notification()

    assert status_code == 200
    assert result["data"] == {"notification": None}


def test_get_notification_module_exception():
    """Test error handling when get_notification raises a RequestException (Sieve command failed)."""
    fake_module = FakeModuleFilter()
    fake_module.get_section = lambda *args: (_ for _ in ()).throw(
        RequestException("Sieve command failed", err.ERROR_SIEVE_COMMAND_FAILED)
    )
    interface = make_interface(fake_module)

    result, status_code = interface.get_notification()

    assert result["error_code"] == "S001504"
    assert status_code >= 500
