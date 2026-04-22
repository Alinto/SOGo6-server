"""
Ces tests utilisent un fake ClientSQL pour tester la logique métier du module.
"""

from unittest import mock
import pytest

from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.exceptions import BugException, RequestException, AggravatedException
from app.config.db import tables as tbl
from app.utils import errors as err


class FakeClientSQL:
    """Fake ClientSQL for testing ModuleUserProfile."""

    def __init__(self):
        # Default results
        self.select_result = []
        self.insert_result = 1
        self.update_result = 1
        self.delete_result = 1

        # Track method calls
        self.connect_called = False
        self.select_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

        # Connection state
        self.connected = False

    def connect(self):
        """Simulate database connection."""
        self.connected = True
        self.connect_called = True

    def select_from_table(self, table_name, column_tuple, condition=None):
        """Simulate SELECT query."""
        self.select_calls.append({
            'table': table_name,
            'columns': column_tuple,
            'condition': condition
        })
        return self.select_result

    def insert_in_table(self, table_name, column_tuple, values_tuple):
        """Simulate INSERT query."""
        self.insert_calls.append({
            'table': table_name,
            'columns': column_tuple,
            'values': values_tuple
        })
        if isinstance(self.insert_result, Exception):
            raise self.insert_result
        return self.insert_result

    def update_in_table(self, table_name, column_tuple, values_list, condition):
        """Simulate UPDATE query."""
        self.update_calls.append({
            'table': table_name,
            'columns': column_tuple,
            'values': values_list,
            'condition': condition
        })
        if isinstance(self.update_result, Exception):
            raise self.update_result
        return self.update_result

    def delete_from_table(self, table_name, condition):
        """Simulate DELETE query."""
        self.delete_calls.append({
            'table': table_name,
            'condition': condition
        })
        return self.delete_result


class FakeProcessSettings:
    """Fake ProcessSetting for testing."""

    def __init__(self):
        self.SOGO_P_DB_TYPE = "SQL"

    def get_db_settings(self):
        """Return fake database settings."""
        return {
            'host': 'localhost',
            'port': 3306,
            'user': 'test',
            'password': 'test',
            'database': 'test_db'
        }


class FakeUser:
    """Fake User for testing."""

    def __init__(self, uid='testuser', mail='testuser@example.com', cn='Test User'):
        self.uid = uid
        self.mail = mail
        self.cn = cn


def patch_import_manager(monkeypatch, fake_client):
    """Patch import_and_instantiate_manager to return fake client."""
    monkeypatch.setattr(
        "app.module.user.ModuleUserProfile.import_and_instantiate_manager",
        lambda module_path, module_and_class_name, module_args: fake_client
    )


def get_default_domain_settings():
    """Return default domain settings for testing."""
    return {
        "USER_MODULE_SETTINGS": {
            "SOGO_D_IDENTITIES_ENABLED": True,
            "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
            "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
            "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
            "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
            "SOGO_D_SIGNATURE_SIZE_LIMIT": 100
        },
        "USER_DEFAULT": {}
    }


# ========== Tests for initialization ==========

def test_module_init_success(monkeypatch):
    """Test ModuleUserProfile initialization."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()

    module = ModuleUserProfile(process_settings, domain_settings)

    assert module.sogo_db_manager == fake_client
    assert module.process_settings == process_settings
    assert module.user_domain == domain_settings


# ========== Tests for is_user_profile_present ==========

def test_is_user_profile_present_found(monkeypatch):
    """Test checking if user profile exists - found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [('testuser',)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    result = module.is_user_profile_present('testuser')

    assert result is True
    assert fake_client.connect_called is True
    assert len(fake_client.select_calls) == 1


def test_is_user_profile_present_not_found(monkeypatch):
    """Test checking if user profile exists - not found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = []
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    result = module.is_user_profile_present('testuser')

    assert result is False


def test_is_user_profile_present_duplicate(monkeypatch):
    """Test checking if user profile exists - duplicate found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [('testuser',), ('testuser',)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    with pytest.raises(AggravatedException):
        module.is_user_profile_present('testuser')


# ========== Tests for create_user_profile ==========

def test_create_user_profile_success(monkeypatch):
    """Test creating a user profile."""
    fake_client = FakeClientSQL()
    fake_client.insert_result = 1
    patch_import_manager(monkeypatch, fake_client)

    mock_calendar_cls = mock.MagicMock()
    monkeypatch.setattr("app.module.user.ModuleUserProfile.ModuleCalendar", mock_calendar_cls)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    module.create_user_profile(user)

    assert len(fake_client.insert_calls) == 1
    assert fake_client.insert_calls[0]['table'] == tbl.TABLE_USER.name
    mock_calendar_cls.return_value.create_personal_calendar.assert_called_once_with(user.uid)


def test_create_user_profile_insert_failed(monkeypatch):
    """Test creating user profile with insert failure."""
    fake_client = FakeClientSQL()
    fake_client.insert_result = BugException("Insert failed", err.ERROR_USER_PROFILE_CREATION_FAILED)
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()

    with pytest.raises(BugException):
        module.create_user_profile(user)


def test_create_user_profile_wrong_row_count(monkeypatch):
    """Test creating user profile with wrong row count."""
    fake_client = FakeClientSQL()
    fake_client.insert_result = 0
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()

    with pytest.raises(BugException):
        module.create_user_profile(user)


# ========== Tests for _get_user_column ==========

def test_get_user_column_success(monkeypatch):
    """Test getting a user column."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({'key': 'value'},)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    result = module._get_user_column('testuser', tbl.COL_USER_DEFAULTS.name)

    assert result == {'key': 'value'}
    assert len(fake_client.select_calls) == 1


def test_get_user_column_not_found(monkeypatch):
    """Test getting a user column - user not found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = []
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    with pytest.raises(RequestException):
        module._get_user_column('testuser', tbl.COL_USER_DEFAULTS.name)


def test_get_user_column_duplicate(monkeypatch):
    """Test getting a user column - duplicate users."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({'key': 'value'},), ({'key': 'value2'},)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    with pytest.raises(AggravatedException):
        module._get_user_column('testuser', tbl.COL_USER_DEFAULTS.name)


def test_get_user_column_none_value(monkeypatch):
    """Test getting a user column with None value."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [(None,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    result = module._get_user_column('testuser', tbl.COL_USER_DEFAULTS.name)

    assert result == {}


# ========== Tests for _update_user_column ==========

def test_update_user_column_success(monkeypatch):
    """Test updating a user column."""
    fake_client = FakeClientSQL()
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    module._update_user_column('testuser', tbl.COL_USER_DEFAULTS.name, {'key': 'value'})

    assert len(fake_client.update_calls) == 1
    assert fake_client.update_calls[0]['table'] == tbl.TABLE_USER.name


def test_update_user_column_not_found(monkeypatch):
    """Test updating a user column - user not found."""
    fake_client = FakeClientSQL()
    fake_client.update_result = 0
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    with pytest.raises(RequestException):
        module._update_user_column('testuser', tbl.COL_USER_DEFAULTS.name, {'key': 'value'})


def test_update_user_column_duplicate(monkeypatch):
    """Test updating a user column - duplicate users."""
    fake_client = FakeClientSQL()
    fake_client.update_result = 2
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    with pytest.raises(AggravatedException):
        module._update_user_column('testuser', tbl.COL_USER_DEFAULTS.name, {'key': 'value'})


# ========== Tests for list_accounts ==========

def test_list_accounts_main_only(monkeypatch):
    """Test listing accounts with only main account."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }

    def select_side_effect(*args, **kwargs):
        # First call returns main_account, second call returns empty external_accounts
        if not hasattr(select_side_effect, 'call_count'):
            select_side_effect.call_count = 0
        select_side_effect.call_count += 1

        if select_side_effect.call_count == 1:
            return [(main_account,)]
        return [({},)]

    fake_client.select_from_table = select_side_effect
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.list_accounts(user)

    assert len(result) == 1
    assert result[0]['id'] == '0'
    assert 'identities' in result[0]


def test_list_accounts_with_external(monkeypatch):
    """Test listing accounts with external accounts."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }
    external_accounts = {
        'hash123': {
            'name': 'External Account',
            'mail_server': {},
            'mail_outgoing': {},
            'identities': [],
            'receipts': {},
            'certificates': {}
        }
    }

    def select_side_effect(*args, **kwargs):
        # First call returns main_account, second call returns external_accounts
        if not hasattr(select_side_effect, 'call_count'):
            select_side_effect.call_count = 0
        select_side_effect.call_count += 1

        if select_side_effect.call_count == 1:
            return [(main_account,)]
        return [(external_accounts,)]

    fake_client.select_from_table = select_side_effect
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.list_accounts(user)

    assert len(result) == 2
    assert result[0]['id'] == '0'
    assert result[1]['id'] == 'hash123'


def test_list_accounts_identities_disabled(monkeypatch):
    """Test listing accounts when identities are disabled."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [
            {'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'},
            {'mail': 'alias@example.com', 'name': 'Alias', 'reply-to': 'alias@example.com'}
        ],
        'receipts': {},
        'certificates': {}
    }

    def select_side_effect(*args, **kwargs):
        # First call returns main_account, second call returns empty external_accounts
        if not hasattr(select_side_effect, 'call_count'):
            select_side_effect.call_count = 0
        select_side_effect.call_count += 1

        if select_side_effect.call_count == 1:
            return [(main_account,)]
        return [({},)]

    fake_client.select_from_table = select_side_effect
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_ENABLED"] = False
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.list_accounts(user)

    # Should only keep first identity when identities disabled
    assert len(result[0]['identities']) == 1


# ========== Tests for get_account_detail ==========

def test_get_account_detail_main_account(monkeypatch):
    """Test getting main account detail."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }
    fake_client.select_result = [(main_account,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.get_account_detail(user, '0')

    assert 'identities' in result
    assert len(result['identities']) == 1


def test_get_account_detail_external_account(monkeypatch):
    """Test getting external account detail."""
    fake_client = FakeClientSQL()
    external_accounts = {
        'hash123': {
            'name': 'External Account',
            'mail_server': {},
            'mail_outgoing': {},
            'identities': [],
            'receipts': {},
            'certificates': {}
        }
    }
    fake_client.select_result = [(external_accounts,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.get_account_detail(user, 'hash123')

    assert result['name'] == 'External Account'


def test_get_account_detail_not_found(monkeypatch):
    """Test getting external account detail - not found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({},)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()

    with pytest.raises(RequestException):
        module.get_account_detail(user, 'nonexistent')


# ========== Tests for create_external_account ==========

def test_create_external_account_success(monkeypatch):
    """Test creating an external account."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({},)]
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    account_data = {
        'name': 'New External Account',
        'mail_server': {'host': 'imap.example.com', 'password': 'secret'},
        'mail_outgoing': {'host': 'smtp.example.com', 'password': 'secret'},
        'identities': [{'mail': 'external@example.com', 'name': 'External'}],
        'receipts': {},
        'certificates': {}
    }

    result = module.create_external_account('testuser', account_data)

    assert 'id' in result
    assert result['name'] == 'New External Account'
    assert len(fake_client.update_calls) == 1


def test_create_external_account_signature_too_large(monkeypatch):
    """Test creating external account with signature exceeding size limit."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({},)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_SIGNATURE_SIZE_LIMIT"] = 1  # 1 KB limit
    module = ModuleUserProfile(process_settings, domain_settings)

    large_signature = 'x' * 2000  # 2 KB signature
    account_data = {
        'name': 'New External Account',
        'mail_server': {},
        'mail_outgoing': {},
        'identities': [{'mail': 'external@example.com', 'name': 'External', 'signatures': {'sig1': large_signature}}],
        'receipts': {},
        'certificates': {}
    }

    with pytest.raises(RequestException):
        module.create_external_account('testuser', account_data)


# ========== Tests for update_external_account ==========

def test_update_external_account_success(monkeypatch):
    """Test updating an external account."""
    fake_client = FakeClientSQL()
    existing_account = {
        'hash123': {
            'name': 'Old Name',
            'mail_server': {},
            'mail_outgoing': {},
            'identities': [],
            'receipts': {},
            'certificates': {}
        }
    }
    fake_client.select_result = [(existing_account,)]
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    update_data = {'name': 'New Name'}

    result = module.update_external_account(user, 'hash123', update_data)

    assert result['id'] == 'hash123'
    assert result['name'] == 'New Name'
    assert len(fake_client.update_calls) == 1


def test_update_external_account_not_found(monkeypatch):
    """Test updating external account - not found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({},)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()

    with pytest.raises(RequestException):
        module.update_external_account(user, 'nonexistent', {'name': 'New Name'})


# ========== Tests for delete_external_account ==========

def test_delete_external_account_success(monkeypatch):
    """Test deleting an external account."""
    fake_client = FakeClientSQL()
    existing_accounts = {
        'hash123': {
            'name': 'Account to Delete',
            'mail_server': {},
            'mail_outgoing': {},
            'identities': [],
            'receipts': {},
            'certificates': {}
        }
    }
    fake_client.select_result = [(existing_accounts,)]
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    module.delete_external_account(user, 'hash123')

    assert len(fake_client.update_calls) == 1


def test_delete_external_account_not_found(monkeypatch):
    """Test deleting external account - not found."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [({},)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()

    with pytest.raises(RequestException):
        module.delete_external_account(user, 'nonexistent')


# ========== Tests for update_main_account ==========

def test_update_main_account_success(monkeypatch):
    """Test updating main account."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }
    fake_client.select_result = [(main_account,)]
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    update_data = {
        'identities': [{'mail': 'test@example.com', 'name': 'New Name', 'reply-to': 'test@example.com'}]
    }

    result = module.update_main_account(user, update_data)

    assert result['id'] == '0'
    assert len(fake_client.update_calls) == 1


def test_update_main_account_no_identities(monkeypatch):
    """Test updating main account with no identities."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }
    fake_client.select_result = [(main_account,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    update_data = {'identities': None}

    with pytest.raises(RequestException):
        module.update_main_account(user, update_data)


def test_update_main_account_identities_forbidden(monkeypatch):
    """Test updating main account when multiple identities are forbidden."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }
    fake_client.select_result = [(main_account,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_ENABLED"] = False
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    update_data = {
        'identities': [
            {'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'},
            {'mail': 'alias@example.com', 'name': 'Alias', 'reply-to': 'alias@example.com'}
        ]
    }

    with pytest.raises(RequestException):
        module.update_main_account(user, update_data)


def test_update_main_account_custom_from_forbidden(monkeypatch):
    """Test updating main account when custom from is forbidden."""
    fake_client = FakeClientSQL()
    main_account = {
        'identities': [{'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}],
        'receipts': {},
        'certificates': {}
    }
    fake_client.select_result = [(main_account,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED"] = False
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser(mail='test@example.com')
    update_data = {
        'identities': [{'mail': 'different@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'}]
    }

    with pytest.raises(RequestException):
        module.update_main_account(user, update_data)


# ========== Tests for get_user_preferences ==========

def test_get_user_preferences_success(monkeypatch):
    """Test getting user preferences."""
    fake_client = FakeClientSQL()
    preferences = {'MAIL': {'theme': 'dark'}, 'CALENDAR': {'defaultView': 'week'}}
    fake_client.select_result = [(preferences,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    result = module.get_user_preferences('testuser')

    assert result == preferences


# ========== Tests for get_partial_user_preferences ==========

def test_get_partial_user_preferences_success(monkeypatch):
    """Test getting partial user preferences."""
    fake_client = FakeClientSQL()
    preferences = {'MAIL': {'theme': 'dark'}, 'CALENDAR': {'defaultView': 'week'}}
    fake_client.select_result = [(preferences,)]
    patch_import_manager(monkeypatch, fake_client)

    # Mock user_settings_dict
    mock_schema = mock.Mock()
    mock_schema.subparent = 'MAIL'

    with mock.patch('app.module.user.ModuleUserProfile.user_settings_dict', {'mail': mock_schema}):
        process_settings = FakeProcessSettings()
        domain_settings = get_default_domain_settings()
        module = ModuleUserProfile(process_settings, domain_settings)

        result = module.get_partial_user_preferences('testuser', 'mail')

        assert 'MAIL' in result


def test_get_partial_user_preferences_unknown_subparent(monkeypatch):
    """Test getting partial user preferences with unknown subparent."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    with mock.patch('app.module.user.ModuleUserProfile.user_settings_dict', {}):
        process_settings = FakeProcessSettings()
        domain_settings = get_default_domain_settings()
        module = ModuleUserProfile(process_settings, domain_settings)

        with pytest.raises(RequestException):
            module.get_partial_user_preferences('testuser', 'unknown')


# ========== Tests for update_user_preferences ==========

def test_update_user_preferences_full_success(monkeypatch):
    """Test updating full user preferences."""
    fake_client = FakeClientSQL()
    current_prefs = {'MAIL': {'theme': 'light'}}
    fake_client.select_result = [(current_prefs,)]
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    # Mock the validation function
    with mock.patch('app.module.user.ModuleUserProfile.check_data_for_sogo_schemas', return_value={'MAIL': {'theme': 'dark'}}):
        process_settings = FakeProcessSettings()
        domain_settings = get_default_domain_settings()
        module = ModuleUserProfile(process_settings, domain_settings)

        new_data = {'MAIL': {'theme': 'dark'}}
        result = module.update_user_preferences('testuser', new_data, subparent=None)

        assert result == {'MAIL': {'theme': 'dark'}}


def test_update_user_preferences_partial_success(monkeypatch):
    """Test updating partial user preferences."""
    fake_client = FakeClientSQL()
    current_prefs = {'MAIL': {'theme': 'light'}, 'CALENDAR': {'defaultView': 'week'}}
    fake_client.select_result = [(current_prefs,)]
    fake_client.update_result = 1
    patch_import_manager(monkeypatch, fake_client)

    # Mock user_settings_dict and validation
    mock_schema = mock.Mock()
    mock_schema.subparent = 'MAIL'

    with mock.patch('app.module.user.ModuleUserProfile.user_settings_dict', {'mail': mock_schema}), \
         mock.patch('app.module.user.ModuleUserProfile.check_data_for_sogo_schemas', return_value={'MAIL': {'theme': 'dark'}, 'CALENDAR': {'defaultView': 'week'}}):

        process_settings = FakeProcessSettings()
        domain_settings = get_default_domain_settings()
        module = ModuleUserProfile(process_settings, domain_settings)

        new_data = {'theme': 'dark'}
        result = module.update_user_preferences('testuser', new_data, subparent='mail')

        assert result == {'theme': 'dark'}


# ========== Tests for get_delegations_given ==========

def test_get_delegations_given_success(monkeypatch):
    """Test getting delegations given."""
    fake_client = FakeClientSQL()
    delegations = ['user1@example.com', 'user2@example.com']
    fake_client.select_result = [(delegations,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.get_delegations_given(user)

    assert result == delegations


def test_get_delegations_given_empty(monkeypatch):
    """Test getting delegations given - empty."""
    fake_client = FakeClientSQL()
    fake_client.select_result = [(None,)]
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()
    result = module.get_delegations_given(user)

    assert result == []


# ========== Tests for add_delegation_given ==========

def test_add_delegation_given_not_implemented(monkeypatch):
    """Test that add_delegation_given raises NotImplementedError."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser()

    with pytest.raises(NotImplementedError):
        module.add_delegation_given(user, 'delegate@example.com')


# ========== Tests for _validate_signatures_size ==========

def test_validate_signatures_size_no_limit(monkeypatch):
    """Test signature validation with no size limit."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_SIGNATURE_SIZE_LIMIT"] = 0  # No limit
    module = ModuleUserProfile(process_settings, domain_settings)

    identities = [
        {'mail': 'test@example.com', 'signatures': {'sig1': 'x' * 10000}}
    ]

    # Should not raise exception
    module._validate_signatures_size(identities)


def test_validate_signatures_size_within_limit(monkeypatch):
    """Test signature validation within size limit."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_SIGNATURE_SIZE_LIMIT"] = 10  # 10 KB limit
    module = ModuleUserProfile(process_settings, domain_settings)

    identities = [
        {'mail': 'test@example.com', 'signatures': {'sig1': 'x' * 100}}
    ]

    # Should not raise exception
    module._validate_signatures_size(identities)


def test_validate_signatures_size_exceeds_limit(monkeypatch):
    """Test signature validation exceeding size limit."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_SIGNATURE_SIZE_LIMIT"] = 1  # 1 KB limit
    module = ModuleUserProfile(process_settings, domain_settings)

    identities = [
        {'mail': 'test@example.com', 'signatures': {'sig1': 'x' * 2000}}
    ]

    with pytest.raises(RequestException):
        module._validate_signatures_size(identities)


# ========== Tests for _clean_main_account ==========

def test_clean_main_account_identities_disabled(monkeypatch):
    """Test cleaning main account with identities disabled."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_ENABLED"] = False
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser(mail='test@example.com', cn='Test User')
    main_account = {
        'identities': [
            {'mail': 'test@example.com', 'name': 'Test User', 'reply-to': 'test@example.com'},
            {'mail': 'alias@example.com', 'name': 'Alias', 'reply-to': 'alias@example.com'}
        ]
    }

    module._clean_main_account(user, main_account)

    # Should keep only first identity
    assert len(main_account['identities']) == 1


def test_clean_main_account_custom_fields_disabled(monkeypatch):
    """Test cleaning main account with custom fields disabled."""
    fake_client = FakeClientSQL()
    patch_import_manager(monkeypatch, fake_client)

    process_settings = FakeProcessSettings()
    domain_settings = get_default_domain_settings()
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED"] = False
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED"] = False
    domain_settings["USER_MODULE_SETTINGS"]["SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED"] = False
    module = ModuleUserProfile(process_settings, domain_settings)

    user = FakeUser(mail='test@example.com', cn='Test User')
    main_account = {
        'identities': [
            {'mail': 'custom@example.com', 'name': 'Custom Name', 'reply-to': 'custom@example.com'}
        ]
    }

    module._clean_main_account(user, main_account)

    # Should override with user's actual values
    assert main_account['identities'][0]['mail'] == 'test@example.com'
    assert main_account['identities'][0]['name'] == 'Test User'
    assert main_account['identities'][0]['reply-to'] == 'test@example.com'
