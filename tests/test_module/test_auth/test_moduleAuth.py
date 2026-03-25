"""
Tests unitaires pour ModuleAuth (Module layer).
Ces tests utilisent des fakes pour tester la logique métier du module.
"""
import pytest
from unittest import mock

from app.module.auth.ModuleAuth import ModuleAuth
from app.utils.exceptions import RequestException


class FakeClientSQL:
    """Fake ClientSQL for testing ModuleAuth."""

    def __init__(self):
        self.connect_called = False
        self.select_result = []
        self.select_calls = []

    def connect(self):
        """Simulate database connection."""
        self.connect_called = True

    def select_from_table(self, table_name, column_tuple, condition=None):
        """Simulate selecting from table."""
        self.select_calls.append({
            'table': table_name,
            'columns': column_tuple,
            'condition': condition
        })
        # Return iterator over results (each row is a tuple of column values)
        return iter(self.select_result)


class FakeProcessSettings:
    """Fake ProcessSetting for testing."""

    def __init__(self):
        self.SOGO_P_DB_TYPE = "MySQL"
        self.SOGO_P_VOUCHER_SECRET = "a" * 32

    def get_db_settings(self):
        """Return fake DB settings."""
        return {
            'host': 'localhost',
            'port': 3306,
            'user': 'test',
            'password': 'test',
            'database': 'test'
        }


class FakeSystemSettings:
    """Fake SystemSettingsObj for testing."""

    def __init__(self):
        self.SOGO_S_DO_DOMAIN = True
        self.SOGO_S_DOMAINLESS_LOGIN = False
        self.SOGO_S_KNOWN_DOMAIN = ["example.com", "test.com"]
        self.SOGO_S_REJECT_UNKNOWN_DOMAIN = True


class FakeAuthSettings:
    """Fake AuthSettingsObj for testing."""

    def __init__(self, auth_type="plain", pwd_recovery=False):
        self.SOGO_D_AUTH_TYPE = auth_type
        self.SOGO_D_PWD_RECOVERY = pwd_recovery


class FakeUserSourceSettings:
    """Fake UserSourceSettingsObj for testing."""

    def __init__(self, source_data=None):
        self.data = source_data or {}


class FakeUser:
    """Fake User for testing."""

    def __init__(self, uid='testuser@example.com', password='password'):
        self.uid = uid
        self.password = password
        self.domain = None
        self.is_domainless = False

    def get_user_session(self):
        """Return fake user session."""
        return {
            'uid': self.uid,
            'domain': self.domain,
            'session_id': 'fake-session-id'
        }


class FakeVoucherUserService:
    """Fake VoucherUserService for testing."""

    def __init__(self, process_settings):
        self.process_settings = process_settings

    def generate_voucher_from_user(self, user):
        """Generate fake voucher."""
        return "fake-jwt-token-12345"


def patch_import_manager(monkeypatch, fake_client):
    """Patch import_and_instantiate_manager to return fake client."""
    monkeypatch.setattr(
        "app.module.auth.ModuleAuth.import_and_instantiate_manager",
        lambda module_path, module_and_class_name, module_args: fake_client
    )


def get_default_auth_settings():
    """Return default auth settings for testing."""
    return FakeAuthSettings(auth_type="plain")


def get_default_user_sources():
    """Return default user sources for testing."""
    return {
        "source1": FakeUserSourceSettings({"type": "ldap", "host": "ldap.example.com"})
    }


# ========== Tests for initialization ==========

def test_module_init_success():
    """Test ModuleAuth initialization."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    assert module.process_settings == process
    assert module.do_domains is True
    assert module.domainless is False
    assert module.known_domains == ["example.com", "test.com"]
    assert module.reject_unknown is True
    assert module.default_auth == auth_settings
    assert module.default_us == user_sources


def test_module_init_domainless_enabled():
    """Test ModuleAuth initialization with domainless login enabled."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_DOMAINLESS_LOGIN = True
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    assert module.domainless is True


# ========== Tests for _check_domain ==========

def test_check_domain_domainless_enabled():
    """Test _check_domain when domainless login is enabled."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_DOMAINLESS_LOGIN = True
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    result = module._check_domain("user@example.com")
    assert result == ""


def test_check_domain_with_valid_domain():
    """Test _check_domain with valid domain."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    result = module._check_domain("user@example.com")
    assert result == "example.com"


def test_check_domain_no_domain_given():
    """Test _check_domain when no domain is given but required."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with pytest.raises(RequestException, match="No domain given for auth when this is required"):
        module._check_domain("username")


def test_check_domain_unknown_domain_rejected():
    """Test _check_domain when unknown domain is rejected."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with pytest.raises(RequestException, match="Domain given for auth is not registered"):
        module._check_domain("user@unknown.com")


def test_check_domain_unknown_domain_allowed():
    """Test _check_domain when unknown domain is allowed."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_REJECT_UNKNOWN_DOMAIN = False
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    result = module._check_domain("user@unknown.com")
    assert result == "unknown.com"


# ========== Tests for _get_domain_auth_and_user_source_settings ==========

def test_get_domain_settings_no_domain():
    """Test getting domain settings when no domain is provided."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    auth, sources = module._get_domain_auth_and_user_source_settings("")  # noqa: SLF001

    assert auth == auth_settings
    assert sources == user_sources


def test_get_domain_settings_domains_disabled():
    """Test getting domain settings when domain handling is disabled."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_DO_DOMAIN = False
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    auth, sources = module._get_domain_auth_and_user_source_settings("example.com")  # noqa: SLF001

    assert auth == auth_settings
    assert sources == user_sources


def test_get_domain_settings_from_database(monkeypatch):
    """Test getting domain settings from database."""
    fake_client = FakeClientSQL()
    # Result format: list of tuples, each tuple contains column values
    # result[0][0] means first row, first column
    fake_client.select_result = [
        ({
            "AUTH_SETTINGS": {
                "SOGO_D_AUTH_TYPE": "ldap"
            },
            "USER_SOURCE": {
                "source1": {
                    "type": "ldap",
                    "host": "ldap.domain.com"
                }
            }
        },)
    ]
    patch_import_manager(monkeypatch, fake_client)

    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with mock.patch('app.module.auth.ModuleAuth.AuthSettingsObj') as mock_auth:
        with mock.patch('app.module.auth.ModuleAuth.UserSourceSettingsObj') as mock_source:
            mock_auth.return_value = FakeAuthSettings(auth_type="ldap")
            mock_source.return_value = FakeUserSourceSettings({"type": "ldap"})

            _auth, _sources = module._get_domain_auth_and_user_source_settings("example.com")  # noqa: SLF001

            assert fake_client.connect_called is True
            assert len(fake_client.select_calls) == 1


def test_get_domain_settings_not_found_in_database(monkeypatch):
    """Test getting domain settings when domain not found in database."""
    fake_client = FakeClientSQL()
    fake_client.select_result = []
    patch_import_manager(monkeypatch, fake_client)

    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    # Should return default settings when domain not found
    auth, sources = module._get_domain_auth_and_user_source_settings("example.com")  # noqa: SLF001

    assert auth == auth_settings
    assert sources == user_sources


# ========== Tests for get_login_mech ==========

def test_get_login_mech_plain(monkeypatch):
    """Test getting login mechanism for plain authentication."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)
    
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    result = module.get_login_mech("user@example.com")

    assert result['kind'] == "plain"
    assert result['location'] == ""


def test_get_login_mech_with_invalid_domain():
    """Test getting login mechanism with invalid domain."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with pytest.raises(RequestException):
        module.get_login_mech("user@unknown.com")


def test_get_login_mech_domainless():
    """Test getting login mechanism with domainless login."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_DOMAINLESS_LOGIN = True
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    result = module.get_login_mech("username")

    assert result['kind'] == "plain"
    assert result['location'] == ""


# ========== Tests for get_user_and_domain_user_sources ==========

def test_get_user_domainless_enabled(monkeypatch):
    """Test getting user when domainless login is enabled."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_DOMAINLESS_LOGIN = True
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with mock.patch('app.module.auth.ModuleAuth.User') as mock_user:
        mock_user.return_value = FakeUser('username', 'password')
        _user, sources = module.get_user_and_domain_user_sources("username", "password")

        # Verify User was called with is_domainless=True
        mock_user.assert_called_once_with("username", "password", is_domainless=True)
        assert sources == user_sources


def test_get_user_with_domain(monkeypatch):
    """Test getting user with domain."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)
    
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with mock.patch('app.module.auth.ModuleAuth.User') as mock_user:
        mock_user.return_value = FakeUser('user@example.com', 'password')
        _user, sources = module.get_user_and_domain_user_sources("user@example.com", "password")

        # Verify User was called with domain parameter
        mock_user.assert_called_once_with("user@example.com", "password", domain="example.com")
        assert sources == user_sources


def test_get_user_invalid_domain():
    """Test getting user with invalid domain."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with pytest.raises(RequestException):
        module.get_user_and_domain_user_sources("user@unknown.com", "password")


def test_get_user_no_domain_when_required():
    """Test getting user without domain when domain is required."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    with pytest.raises(RequestException):
        module.get_user_and_domain_user_sources("username", "password")


# ========== Tests for generate_voucher_from_user ==========

def test_generate_voucher_success(monkeypatch):
    """Test generating voucher from authenticated user."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    fake_user = FakeUser('user@example.com', 'password')

    with mock.patch('app.module.auth.ModuleAuth.VoucherUserService') as mock_service:
        mock_service.return_value = FakeVoucherUserService(process)

        result = module.generate_voucher_from_user(fake_user)

        assert 'jwt_token' in result
        assert result['jwt_token'] == "fake-jwt-token-12345"
        mock_service.assert_called_once_with(process)


def test_generate_voucher_with_different_user(monkeypatch):
    """Test generating voucher for different user."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    fake_user = FakeUser('admin@test.com', 'admin123')

    with mock.patch('app.module.auth.ModuleAuth.VoucherUserService') as mock_service:
        fake_voucher_service = FakeVoucherUserService(process)
        mock_service.return_value = fake_voucher_service

        result = module.generate_voucher_from_user(fake_user)

        assert 'jwt_token' in result


# ========== Integration-style tests ==========

def test_full_auth_flow_with_domain(monkeypatch):
    """Test full authentication flow with domain."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)
    
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    # Step 1: Get login mechanism
    login_mech = module.get_login_mech("user@example.com")
    assert login_mech['kind'] == "plain"

    # Step 2: Get user and sources
    with mock.patch('app.module.auth.ModuleAuth.User') as mock_user:
        mock_user.return_value = FakeUser('user@example.com', 'password')
        user, sources = module.get_user_and_domain_user_sources("user@example.com", "password")
        assert sources == user_sources

        # Step 3: Generate voucher
        with mock.patch('app.module.auth.ModuleAuth.VoucherUserService') as mock_service:
            mock_service.return_value = FakeVoucherUserService(process)
            result = module.generate_voucher_from_user(user)
            assert 'jwt_token' in result


def test_full_auth_flow_domainless(monkeypatch):
    """Test full authentication flow with domainless login."""
    process = FakeProcessSettings()
    system = FakeSystemSettings()
    system.SOGO_S_DOMAINLESS_LOGIN = True
    auth_settings = get_default_auth_settings()
    user_sources = get_default_user_sources()

    module = ModuleAuth(process, system, auth_settings, user_sources)

    # Step 1: Get login mechanism
    login_mech = module.get_login_mech("username")
    assert login_mech['kind'] == "plain"

    # Step 2: Get user and sources
    with mock.patch('app.module.auth.ModuleAuth.User') as mock_user:
        mock_user.return_value = FakeUser('username', 'password')
        user, sources = module.get_user_and_domain_user_sources("username", "password")
        assert sources == user_sources

        # Step 3: Generate voucher
        with mock.patch('app.module.auth.ModuleAuth.VoucherUserService') as mock_service:
            mock_service.return_value = FakeVoucherUserService(process)
            result = module.generate_voucher_from_user(user)
            assert 'jwt_token' in result
