"""
Tests unitaires pour ClientSieve (Manager layer).
Ces tests utilisent des mock objects pour simuler les réponses ManageSieve.
"""
import pytest
from unittest import mock
from sievelib.managesieve import Error as SieveError

from app.manager.mail.ClientSieve import ClientSieve, SIEVE_MASTER_SCRIPT
from app.utils.exceptions import RequestException, BugException
from app.utils import constants as cs
from app.utils.constants import (
    FILTER_SECTION_FILTERS,
    FILTER_SECTION_VACATION,
    FILTER_SECTION_FORWARD,
    FILTER_SECTION_NOTIFICATION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client(server="sieve.example.com", port=4190,
                encryption=cs.SOCKET_ENC_PLAIN,
                auth_mech="plain") -> ClientSieve:
    """Build a ClientSieve with sensible defaults."""
    return ClientSieve(server=server, port=port, encryption=encryption, auth_mech=auth_mech)


def authenticated_client(fake_conn) -> ClientSieve:
    """Return a ClientSieve that looks already connected + authenticated."""
    client = make_client()
    client.connection = fake_conn
    client.connected = True
    client.authenticated = True
    return client


# ---------------------------------------------------------------------------
# Fake Sieve connection (mimics sievelib.managesieve.Client)
# ---------------------------------------------------------------------------

class FakeSieveConnection:
    """Minimal fake that mimics sievelib.managesieve.Client responses."""

    def __init__(self):
        self.logged_in = False
        self.scripts: dict = {}
        self.active_script: str = ""
        self.errmsg: bytes | str | None = None

        # Configurable responses
        self.connect_should_fail = False
        self.connect_return_value = True
        self.putscript_return_value = True
        self.putscript_error_msg: bytes | None = None
        self.deletescript_return_value = True
        self.setactive_return_value = True

    def connect(self, login, password, authz_id="", starttls=False, ssl=False, authmech=None):
        if self.connect_should_fail:
            raise SieveError("Authentication failed")
        self.logged_in = True
        return self.connect_return_value

    def putscript(self, name, content):
        if self.putscript_error_msg is not None:
            self.errmsg = self.putscript_error_msg
            return False
        self.scripts[name] = content
        return self.putscript_return_value

    def deletescript(self, name):
        if name not in self.scripts:
            self.errmsg = b"Script not found"
            return False
        self.scripts.pop(name, None)
        return self.deletescript_return_value

    def setactive(self, name):
        self.active_script = name
        return self.setactive_return_value

    def logout(self):
        self.logged_in = False


# ===========================================================================
# Tests: ClientSieve.__init__
# ===========================================================================

class TestClientSieveInit:
    def test_init_sets_all_attributes(self):
        client = make_client()
        assert client.server == "sieve.example.com"
        assert client.port == 4190
        assert client.encryption == cs.SOCKET_ENC_PLAIN
        assert client.auth_mech == "plain"
        assert client.connection is None
        assert client.connected is False
        assert client.authenticated is False

    def test_init_implicit_tls(self):
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        assert client.encryption == cs.SOCKET_ENC_IMPLICIT_TLS

    def test_init_explicit_tls(self):
        client = make_client(encryption=cs.SOCKET_ENC_EXPLICIT_TLS)
        assert client.encryption == cs.SOCKET_ENC_EXPLICIT_TLS


# ===========================================================================
# Tests: connect
# ===========================================================================

class TestConnect:
    def test_connect_plain_creates_client(self):
        client = make_client(encryption=cs.SOCKET_ENC_PLAIN)
        with mock.patch("app.manager.mail.ClientSieve.Client") as MockClient:
            MockClient.return_value = FakeSieveConnection()
            client.connect()
        assert client.connected is True
        assert client.connection is not None

    def test_connect_implicit_tls_creates_client(self):
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        with mock.patch("app.manager.mail.ClientSieve.Client") as MockClient:
            MockClient.return_value = FakeSieveConnection()
            client.connect()
        assert client.connected is True

    def test_connect_explicit_tls_creates_client(self):
        client = make_client(encryption=cs.SOCKET_ENC_EXPLICIT_TLS)
        with mock.patch("app.manager.mail.ClientSieve.Client") as MockClient:
            MockClient.return_value = FakeSieveConnection()
            client.connect()
        assert client.connected is True

    def test_connect_unknown_encryption_raises_bug_exception(self):
        client = make_client(encryption="UNKNOWN_ENC")
        with pytest.raises(BugException):
            client.connect()


# ===========================================================================
# Tests: login
# ===========================================================================

class TestLogin:
    def test_login_success(self):
        fake_conn = FakeSieveConnection()
        client = make_client()
        client.connection = fake_conn
        client.connected = True

        client.login("user@example.com", "password")

        assert fake_conn.logged_in is True
        assert client.authenticated is True

    def test_login_no_connection_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.login("user@example.com", "password")

    def test_login_sieve_error_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        fake_conn.connect_should_fail = True
        client = make_client()
        client.connection = fake_conn
        client.connected = True

        with pytest.raises(RequestException):
            client.login("user@example.com", "wrong_password")

    def test_login_returns_false_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        fake_conn.connect_return_value = False
        fake_conn.errmsg = b"Authentication failed"
        client = make_client()
        client.connection = fake_conn
        client.connected = True

        with pytest.raises(RequestException):
            client.login("user@example.com", "wrong")

    def test_login_tcp_error_raises_request_exception(self):
        from socket import gaierror
        fake_conn = FakeSieveConnection()
        client = make_client()
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "connect", side_effect=gaierror("Name or service not known")):
            with pytest.raises(RequestException):
                client.login("user@example.com", "password")

    def test_login_implicit_tls_passes_ssl_true(self):
        fake_conn = FakeSieveConnection()
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "connect", wraps=fake_conn.connect) as mock_connect:
            client.login("user@example.com", "password")
            _, kwargs = mock_connect.call_args
            assert kwargs.get("ssl") is True

    def test_login_explicit_tls_passes_starttls_true(self):
        fake_conn = FakeSieveConnection()
        client = make_client(encryption=cs.SOCKET_ENC_EXPLICIT_TLS)
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "connect", wraps=fake_conn.connect) as mock_connect:
            client.login("user@example.com", "password")
            _, kwargs = mock_connect.call_args
            assert kwargs.get("starttls") is True

    def test_login_auth_mech_uppercased(self):
        fake_conn = FakeSieveConnection()
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "connect", wraps=fake_conn.connect) as mock_connect:
            client.login("user@example.com", "password")
            _, kwargs = mock_connect.call_args
            assert kwargs.get("authmech") == "PLAIN"


# ===========================================================================
# Tests: logout
# ===========================================================================

class TestLogout:
    def test_logout_success(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)
        fake_conn.logged_in = True

        client.logout()

        assert fake_conn.logged_in is False
        assert client.connection is None
        assert client.connected is False
        assert client.authenticated is False

    def test_logout_no_connection_does_nothing(self):
        client = make_client()
        client.connection = None
        client.logout()  # must not raise

    def test_logout_sieve_error_silently_ignored(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        with mock.patch.object(fake_conn, "logout", side_effect=SieveError("Disconnect error")):
            client.logout()  # must not raise

        assert client.connection is None
        assert client.connected is False


# ===========================================================================
# Tests: _exec_sieve_method
# ===========================================================================

class TestExecSieveMethod:
    def test_success_returns_value(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        result = client._exec_sieve_method(lambda: "ok")
        assert result == "ok"

    def test_sieve_error_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        with pytest.raises(RequestException):
            client._exec_sieve_method(lambda: (_ for _ in ()).throw(SieveError("Command failed")))

    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client._exec_sieve_method(lambda: None)


# ===========================================================================
# Tests: _get_sieve_error_message
# ===========================================================================

class TestGetSieveErrorMessage:
    def test_no_connection_returns_generic(self):
        client = make_client()
        client.connection = None
        result = client._get_sieve_error_message()
        assert "No connection" in result

    def test_errmsg_none_returns_generic(self):
        fake_conn = FakeSieveConnection()
        fake_conn.errmsg = None
        client = authenticated_client(fake_conn)
        result = client._get_sieve_error_message()
        assert "Unknown error" in result

    def test_errmsg_bytes_decoded(self):
        fake_conn = FakeSieveConnection()
        fake_conn.errmsg = b"Script compilation failed"
        client = authenticated_client(fake_conn)
        result = client._get_sieve_error_message()
        assert result == "Script compilation failed"

    def test_errmsg_string_returned(self):
        fake_conn = FakeSieveConnection()
        fake_conn.errmsg = "Authentication failed"
        client = authenticated_client(fake_conn)
        result = client._get_sieve_error_message()
        assert result == "Authentication failed"


# ===========================================================================
# Tests: _extract_missing_capability
# ===========================================================================

class TestExtractMissingCapability:
    def test_backtick_pattern(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)
        result = client._extract_missing_capability("unknown Sieve capability `notify'")
        assert result == "notify"

    def test_single_quote_pattern(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)
        result = client._extract_missing_capability("unknown Sieve capability 'vacation'")
        assert result == "vacation"

    def test_unknown_command_pattern(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)
        result = client._extract_missing_capability("unknown command 'fileinto'")
        assert result == "fileinto"

    def test_unknown_error_raises_bug_exception(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)
        with pytest.raises(BugException):
            client._extract_missing_capability("some completely unrecognised error message")


# ===========================================================================
# Tests: put_script
# ===========================================================================

class TestPutScript:
    def test_success_returns_true_none(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        success, missing = client.put_script("test-script", 'require [];\nkeep;\n')
        assert success is True
        assert missing is None
        assert "test-script" in fake_conn.scripts

    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.put_script("script", "keep;")

    def test_failure_with_missing_capability_returns_false_capability(self):
        fake_conn = FakeSieveConnection()
        fake_conn.putscript_error_msg = b"unknown Sieve capability `notify'"
        client = authenticated_client(fake_conn)

        success, missing = client.put_script("test", "keep;")
        assert success is False
        assert missing == "notify"

    def test_failure_without_capability_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        fake_conn.putscript_error_msg = b"Disk quota exceeded"
        client = authenticated_client(fake_conn)

        with pytest.raises(RequestException):
            client.put_script("test", "keep;")


# ===========================================================================
# Tests: delete_script
# ===========================================================================

class TestDeleteScript:
    def test_delete_success(self):
        fake_conn = FakeSieveConnection()
        fake_conn.scripts["my-script"] = "keep;"
        client = authenticated_client(fake_conn)

        client.delete_script("my-script")
        assert "my-script" not in fake_conn.scripts

    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.delete_script("my-script")

    def test_delete_nonexistent_script_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        with pytest.raises(RequestException):
            client.delete_script("nonexistent")


# ===========================================================================
# Tests: set_active
# ===========================================================================

class TestSetActive:
    def test_set_active_success(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        client.set_active("sogo-master")
        assert fake_conn.active_script == "sogo-master"

    def test_set_active_empty_string_deactivates(self):
        fake_conn = FakeSieveConnection()
        fake_conn.active_script = "sogo-master"
        client = authenticated_client(fake_conn)

        client.set_active("")
        assert fake_conn.active_script == ""

    def test_set_active_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.set_active("sogo-master")

    def test_set_active_failure_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        fake_conn.setactive_return_value = False
        client = authenticated_client(fake_conn)

        with pytest.raises(RequestException):
            client.set_active("sogo-master")


# ===========================================================================
# Tests: _validate_email
# ===========================================================================

class TestValidateEmail:
    def test_valid_email(self):
        client = make_client()
        assert client._validate_email("user@example.com") is True

    def test_valid_email_with_subdomain(self):
        client = make_client()
        assert client._validate_email("user.name+tag@sub.domain.org") is True

    def test_invalid_email_no_at(self):
        client = make_client()
        assert client._validate_email("notanemail") is False

    def test_invalid_email_no_domain(self):
        client = make_client()
        assert client._validate_email("user@") is False

    def test_empty_string_invalid(self):
        client = make_client()
        assert client._validate_email("") is False


# ===========================================================================
# Tests: _is_valid_time
# ===========================================================================

class TestIsValidTime:
    def test_valid_time(self):
        client = make_client()
        assert client._is_valid_time("14:30") is True
        assert client._is_valid_time("00:00") is True
        assert client._is_valid_time("23:59") is True

    def test_invalid_time_bad_format(self):
        client = make_client()
        assert client._is_valid_time("25:00") is False
        assert client._is_valid_time("not-a-time") is False
        assert client._is_valid_time("14") is False

    def test_invalid_time_empty(self):
        client = make_client()
        assert client._is_valid_time("") is False


# ===========================================================================
# Tests: _parse_vacation_datetime
# ===========================================================================

class TestParseVacationDatetime:
    def test_date_only(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("2026-06-15")
        assert date == "2026-06-15"
        assert time is None
        assert tz == "UTC"

    def test_date_only_with_default_tz(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("2026-06-15", "Europe/Paris")
        assert date == "2026-06-15"
        assert tz == "Europe/Paris"

    def test_datetime_no_tz(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("2026-06-15T14:30:00", "UTC")
        assert date == "2026-06-15"
        assert time == "14:30:00"
        assert tz == "UTC"

    def test_datetime_with_z(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("2026-06-15T14:30:00Z")
        assert date == "2026-06-15"
        assert tz == "UTC"

    def test_datetime_with_plus_offset(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("2026-06-15T14:30:00+0100")
        assert date == "2026-06-15"
        assert "+0100" in tz

    def test_none_returns_none_tuple(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime(None)
        assert date is None
        assert time is None

    def test_empty_string_returns_none(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("")
        assert date is None

    def test_invalid_date_returns_none(self):
        client = make_client()
        date, time, tz = client._parse_vacation_datetime("not-a-date")
        assert date is None


# ===========================================================================
# Tests: _map_field_name
# ===========================================================================

class TestMapFieldName:
    def test_known_fields(self):
        client = make_client()
        assert client._map_field_name("subject") == "subject"
        assert client._map_field_name("from") == "from"
        assert client._map_field_name("to") == "to"

    def test_header_with_custom_header(self):
        client = make_client()
        assert client._map_field_name("header", "X-Custom") == "X-Custom"

    def test_unknown_field_returned_as_is(self):
        client = make_client()
        result = client._map_field_name("unknown_field")
        assert result == "unknown_field"


# ===========================================================================
# Tests: _map_operator_name
# ===========================================================================

class TestMapOperatorName:
    def test_contains(self):
        client = make_client()
        assert client._map_operator_name("contains") == ":contains"

    def test_is_equals(self):
        client = make_client()
        assert client._map_operator_name("is") == ":is"
        assert client._map_operator_name("equals") == ":is"

    def test_starts_with_variants(self):
        client = make_client()
        assert client._map_operator_name("starts-with") == ":startswith"
        assert client._map_operator_name("starts_with") == ":startswith"
        assert client._map_operator_name("startswith") == ":startswith"

    def test_ends_with_variants(self):
        client = make_client()
        assert client._map_operator_name("ends-with") == ":endswith"
        assert client._map_operator_name("ends_with") == ":endswith"

    def test_unknown_operator_returns_with_colon_prefix(self):
        client = make_client()
        result = client._map_operator_name("mycustomop")
        assert result == ":mycustomop"

    def test_already_prefixed_operator_returned_as_is(self):
        client = make_client()
        result = client._map_operator_name(":contains")
        assert result == ":contains"


# ===========================================================================
# Tests: _build_sieve_actions
# ===========================================================================

class TestBuildSieveActions:
    def test_discard_action(self):
        client = make_client()
        actions = client._build_sieve_actions([{"method": "discard", "arguments": {}}])
        assert ("discard",) in actions

    def test_keep_action(self):
        client = make_client()
        actions = client._build_sieve_actions([{"method": "keep", "arguments": {}}])
        assert ("keep",) in actions

    def test_stop_action(self):
        client = make_client()
        actions = client._build_sieve_actions([{"method": "stop", "arguments": {}}])
        assert ("stop",) in actions

    def test_fileinto_action(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "fileinto", "arguments": {"folder": "Junk"}}
        ])
        assert any("Junk" in str(a) for a in actions)

    def test_redirect_action_valid_email(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "redirect", "arguments": {"address": "forward@example.com"}}
        ])
        assert any("forward@example.com" in str(a) for a in actions)

    def test_redirect_action_invalid_email_skipped(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "redirect", "arguments": {"address": "not-an-email"}}
        ])
        assert len(actions) == 0

    def test_copy_action(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "copy", "arguments": {"folder": "Archive"}}
        ])
        assert any("Archive" in str(a) for a in actions)

    def test_removeheader_action(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "removeheader", "arguments": {"header_name": "X-Spam"}}
        ])
        assert any("X-Spam" in str(a) for a in actions)

    def test_unknown_method_skipped(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "unknown_method", "arguments": {}}
        ])
        assert actions == []

    def test_fileinto_no_folder_skipped(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "fileinto", "arguments": {}}
        ])
        assert actions == []

    def test_multiple_actions(self):
        client = make_client()
        actions = client._build_sieve_actions([
            {"method": "fileinto", "arguments": {"folder": "Junk"}},
            {"method": "stop", "arguments": {}},
        ])
        assert len(actions) == 2


# ===========================================================================
# Tests: _build_sieve_conditions / _flatten_rules
# ===========================================================================

class TestBuildSieveConditions:
    def test_empty_rules_returns_empty(self):
        client = make_client()
        result = client._build_sieve_conditions({})
        assert result == []

    def test_single_leaf_rule(self):
        client = make_client()
        rules = {"field": "subject", "operator": "contains", "value": "spam"}
        result = client._build_sieve_conditions(rules)
        assert len(result) == 1
        assert result[0] == ("subject", ":contains", "spam")

    def test_group_rule_with_and(self):
        client = make_client()
        rules = {
            "op": "and",
            "rules": [
                {"field": "subject", "operator": "contains", "value": "spam"},
                {"field": "from", "operator": "is", "value": "evil@bad.com"},
            ]
        }
        result = client._build_sieve_conditions(rules)
        assert len(result) == 1
        assert result[0][0] == "allof"

    def test_group_rule_with_or(self):
        client = make_client()
        rules = {
            "op": "or",
            "rules": [
                {"field": "subject", "operator": "contains", "value": "buy"},
                {"field": "subject", "operator": "contains", "value": "sale"},
            ]
        }
        result = client._build_sieve_conditions(rules)
        assert len(result) == 1
        assert result[0][0] == "anyof"

    def test_empty_group_returns_empty(self):
        client = make_client()
        rules = {"op": "and", "rules": []}
        result = client._build_sieve_conditions(rules)
        assert result == []

    def test_single_rule_in_group_flattened(self):
        client = make_client()
        rules = {
            "op": "and",
            "rules": [
                {"field": "from", "operator": "contains", "value": "spam"}
            ]
        }
        result = client._build_sieve_conditions(rules)
        # Single rule in group should be flattened (not wrapped in allof)
        assert result == [("from", ":contains", "spam")]


# ===========================================================================
# Tests: _build_forward_script
# ===========================================================================

class TestBuildForwardScript:
    def test_single_address_no_copy(self):
        client = make_client()
        script = client._build_forward_script(["fwd@example.com"], keep_copy=0)
        assert 'redirect "fwd@example.com"' in script
        assert "discard" in script
        assert "keep" not in script

    def test_single_address_with_copy(self):
        client = make_client()
        script = client._build_forward_script(["fwd@example.com"], keep_copy=1)
        assert 'redirect "fwd@example.com"' in script
        assert "keep" in script

    def test_multiple_addresses(self):
        client = make_client()
        script = client._build_forward_script(["a@example.com", "b@example.com"])
        assert 'redirect "a@example.com"' in script
        assert 'redirect "b@example.com"' in script


# ===========================================================================
# Tests: _build_notification_script
# ===========================================================================

class TestBuildNotificationScript:
    def test_single_address(self):
        client = make_client()
        config = {
            "notifyAddresses": ["notify@example.com"],
            "notifyMessage": "You have mail",
        }
        script = client._build_notification_script(config)
        assert "enotify" in script
        assert "notify@example.com" in script
        assert "You have mail" in script

    def test_no_addresses_returns_empty_string(self):
        client = make_client()
        config = {"notifyAddresses": [], "notifyMessage": "msg"}
        result = client._build_notification_script(config)
        assert result == ""

    def test_invalid_address_raises_request_exception(self):
        client = make_client()
        config = {"notifyAddresses": ["not-an-email"], "notifyMessage": "msg"}
        with pytest.raises(RequestException):
            client._build_notification_script(config)

    def test_default_message_when_empty(self):
        client = make_client()
        config = {"notifyAddresses": ["user@example.com"], "notifyMessage": ""}
        script = client._build_notification_script(config)
        # Default message should be used
        assert "notify" in script

    def test_multiple_addresses(self):
        client = make_client()
        config = {
            "notifyAddresses": ["a@example.com", "b@example.com"],
            "notifyMessage": "msg",
        }
        script = client._build_notification_script(config)
        assert "a@example.com" in script
        assert "b@example.com" in script


# ===========================================================================
# Tests: _build_vacation_script
# ===========================================================================

class TestBuildVacationScript:
    def test_basic_vacation(self):
        client = make_client()
        config = {
            "enabled": 1,
            "customSubject": "I am away",
            "customSubjectEnabled": True,
            "autoReplyText": "I will be back soon.",
            "startDate": None,
            "endDate": None,
            "timezone": "UTC",
            "startTime": None,
            "endTime": None,
            "weekdaysEnabled": False,
            "days": [],
        }
        script = client._build_vacation_script(config)
        assert "vacation" in script
        assert "I am away" in script
        assert "I will be back soon" in script

    def test_vacation_without_custom_subject_uses_default(self):
        client = make_client()
        config = {
            "enabled": 1,
            "customSubject": "",
            "customSubjectEnabled": False,
            "autoReplyText": "Away.",
            "startDate": None, "endDate": None, "timezone": "UTC",
            "startTime": None, "endTime": None, "weekdaysEnabled": False, "days": [],
        }
        script = client._build_vacation_script(config)
        assert "Auto: Away" in script

    def test_vacation_with_dates_includes_conditions(self):
        client = make_client()
        config = {
            "enabled": 1,
            "customSubject": "Away",
            "customSubjectEnabled": True,
            "autoReplyText": "On vacation.",
            "startDate": "2026-07-01",
            "endDate": "2026-07-31",
            "timezone": "UTC",
            "startTime": None, "endTime": None, "weekdaysEnabled": False, "days": [],
        }
        script = client._build_vacation_script(config)
        assert "2026-07-01" in script
        assert "2026-07-31" in script
        assert "if " in script or "allof" in script

    def test_vacation_with_weekdays(self):
        client = make_client()
        config = {
            "enabled": 1,
            "customSubject": "Away",
            "customSubjectEnabled": True,
            "autoReplyText": "Out.",
            "startDate": None, "endDate": None, "timezone": "UTC",
            "startTime": None, "endTime": None,
            "weekdaysEnabled": True,
            "days": [1, 2, 3, 4, 5],
        }
        script = client._build_vacation_script(config)
        assert "weekday" in script

    def test_vacation_requires_clause(self):
        client = make_client()
        config = {
            "enabled": 1,
            "customSubject": "Away",
            "customSubjectEnabled": True,
            "autoReplyText": "Gone.",
            "startDate": None, "endDate": None, "timezone": "UTC",
            "startTime": None, "endTime": None, "weekdaysEnabled": False, "days": [],
        }
        script = client._build_vacation_script(config)
        assert 'require' in script
        assert '"vacation"' in script


# ===========================================================================
# Tests: _build_vacation_conditions
# ===========================================================================

class TestBuildVacationConditions:
    def test_no_conditions_returns_empty(self):
        client = make_client()
        result = client._build_vacation_conditions()
        assert result == ""

    def test_start_date_only(self):
        client = make_client()
        result = client._build_vacation_conditions(start_date="2026-07-01")
        assert "2026-07-01" in result
        assert "ge" in result

    def test_end_date_only(self):
        client = make_client()
        result = client._build_vacation_conditions(end_date="2026-07-31")
        assert "2026-07-31" in result
        assert "le" in result

    def test_start_and_end_date(self):
        client = make_client()
        result = client._build_vacation_conditions(
            start_date="2026-07-01", end_date="2026-07-31"
        )
        assert "2026-07-01" in result
        assert "2026-07-31" in result
        # Multiple conditions wrapped in allof
        assert "allof" in result or "if" in result

    def test_time_range(self):
        client = make_client()
        result = client._build_vacation_conditions(
            start_time="09:00", end_time="17:00"
        )
        assert "09:00" in result
        assert "17:00" in result

    def test_weekdays(self):
        client = make_client()
        result = client._build_vacation_conditions(
            weekdays_enabled=True, days=[1, 2, 3]
        )
        assert "weekday" in result

    def test_invalid_start_date_skipped(self):
        client = make_client()
        result = client._build_vacation_conditions(start_date="not-a-date")
        # Invalid date should be silently skipped
        assert result == ""


# ===========================================================================
# Tests: _compile_merged_script
# ===========================================================================

class TestCompileMergedScript:
    def test_no_requires_no_header(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        parts = [("filters", "keep;\n")]
        result = client._compile_merged_script(set(), parts)
        assert "require" not in result
        assert "keep" in result

    def test_with_requires(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        parts = [("vacation", 'require ["vacation"];\nvacation :subject "Away" "Out";\n')]
        result = client._compile_merged_script({"vacation"}, parts)
        assert 'require' in result
        assert '"vacation"' in result

    def test_section_headers_included(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        parts = [("filters", "keep;\n"), ("vacation", "discard;\n")]
        result = client._compile_merged_script(set(), parts)
        assert "FILTERS" in result
        assert "VACATION" in result

    def test_require_lines_stripped_from_sections(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        parts = [("vacation", 'require ["vacation"];\nvacation :subject "Away" "Out";\n')]
        result = client._compile_merged_script(set(), parts)
        # The require line should only appear once (merged at top), not duplicated in section
        assert result.count('require') == 1


# ===========================================================================
# Tests: _store_and_activate_script
# ===========================================================================

class TestStoreAndActivateScript:
    def test_success_returns_empty_skipped(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        skipped = client._store_and_activate_script("sogo-master", "keep;")
        assert skipped == set()
        assert fake_conn.active_script == "sogo-master"

    def test_missing_capability_skips_notification_section(self):
        fake_conn = FakeSieveConnection()
        fake_conn.putscript_error_msg = b"unknown Sieve capability `notify'"
        client = authenticated_client(fake_conn)

        requires_set = {"notify"}
        script_parts = [
            (FILTER_SECTION_NOTIFICATION, 'require ["enotify"];\nnotify "mailto:x@y.com";\n'),
        ]

        with mock.patch.object(client, "put_script",
                               side_effect=[(False, "notify"), (True, None)]):
            with mock.patch.object(client, "set_active"):
                skipped = client._store_and_activate_script(
                    "sogo-master", "keep;", requires_set, script_parts
                )
        assert FILTER_SECTION_NOTIFICATION in skipped

    def test_put_script_total_failure_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        fake_conn.putscript_error_msg = b"Disk quota exceeded"
        client = authenticated_client(fake_conn)

        with pytest.raises(RequestException):
            client._store_and_activate_script("sogo-master", "keep;")


# ===========================================================================
# Tests: _cleanup_scripts
# ===========================================================================

class TestCleanupScripts:
    def test_deletes_existing_scripts(self):
        fake_conn = FakeSieveConnection()
        fake_conn.scripts["sogo-rules"] = "keep;"
        client = authenticated_client(fake_conn)

        client._cleanup_scripts(["sogo-rules"])
        assert "sogo-rules" not in fake_conn.scripts

    def test_silently_ignores_nonexistent_scripts(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        client._cleanup_scripts(["nonexistent-script"])  # must not raise

    def test_empty_list_does_nothing(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        client._cleanup_scripts([])  # must not raise


# ===========================================================================
# Tests: _add_filter_to_set
# ===========================================================================

class TestAddFilterToSet:
    def test_filter_without_actions_skipped(self):
        from sievelib.factory import FiltersSet
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_set = FiltersSet("test")
        filter_item = {"name": "empty-filter", "enabled": 1, "actions": [], "rules": {}}
        client._add_filter_to_set(filters_set, filter_item)
        # No filters should be added
        assert len(filters_set.filters) == 0

    def test_filter_with_keep_action_added(self):
        from sievelib.factory import FiltersSet
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_set = FiltersSet("test")
        filter_item = {
            "name": "my-filter",
            "enabled": 1,
            "actions": [{"method": "keep", "arguments": {}}],
            "rules": {},
        }
        client._add_filter_to_set(filters_set, filter_item)
        assert len(filters_set.filters) == 1


# ===========================================================================
# Tests: set_merged_filters
# ===========================================================================

class TestSetMergedFilters:
    def test_not_authenticated_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.set_merged_filters({})

    def test_empty_config_deactivates_and_deletes(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        with mock.patch.object(client, "set_active") as mock_set_active:
            with mock.patch.object(client, "_cleanup_scripts") as mock_cleanup:
                result = client.set_merged_filters({})

        mock_set_active.assert_called_once_with("")
        mock_cleanup.assert_called_once_with([SIEVE_MASTER_SCRIPT])
        assert all(v is False for v in result.values())

    def test_filters_section_activated(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_FILTERS: [
                {
                    "name": "spam-filter",
                    "enabled": 1,
                    "actions": [{"method": "discard", "arguments": {}}],
                    "rules": {"field": "subject", "operator": "contains", "value": "spam"},
                }
            ]
        }

        with mock.patch.object(client, "_store_and_activate_script", return_value=set()):
            result = client.set_merged_filters(filters_config)

        assert result[FILTER_SECTION_FILTERS] is True

    def test_vacation_section_activated(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_VACATION: {
                "enabled": 1,
                "customSubject": "Away",
                "customSubjectEnabled": True,
                "autoReplyText": "Out of office.",
                "startDate": None, "endDate": None, "timezone": "UTC",
                "startTime": None, "endTime": None, "weekdaysEnabled": False, "days": [],
            }
        }

        with mock.patch.object(client, "_store_and_activate_script", return_value=set()):
            result = client.set_merged_filters(filters_config)

        assert result[FILTER_SECTION_VACATION] is True

    def test_forward_section_activated(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_FORWARD: {
                "enabled": 1,
                "forwardAddress": ["fwd@example.com"],
                "keepCopy": 0,
                "alwaysSend": 0,
            }
        }

        with mock.patch.object(client, "_store_and_activate_script", return_value=set()):
            result = client.set_merged_filters(filters_config)

        assert result[FILTER_SECTION_FORWARD] is True

    def test_forward_invalid_email_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_FORWARD: {
                "enabled": 1,
                "forwardAddress": ["not-an-email"],
                "keepCopy": 0,
            }
        }

        with pytest.raises(RequestException):
            client.set_merged_filters(filters_config)

    def test_notification_section_activated(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_NOTIFICATION: {
                "enabled": 1,
                "notifyAddresses": ["notify@example.com"],
                "notifyMessage": "You have new mail",
            }
        }

        with mock.patch.object(client, "_store_and_activate_script", return_value=set()):
            result = client.set_merged_filters(filters_config)

        assert result[FILTER_SECTION_NOTIFICATION] is True

    def test_notification_invalid_email_raises_request_exception(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_NOTIFICATION: {
                "enabled": 1,
                "notifyAddresses": ["not-valid"],
                "notifyMessage": "msg",
            }
        }

        with pytest.raises(RequestException):
            client.set_merged_filters(filters_config)

    def test_notification_skipped_when_not_supported(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_NOTIFICATION: {
                "enabled": 1,
                "notifyAddresses": ["notify@example.com"],
                "notifyMessage": "msg",
            }
        }

        with mock.patch.object(client, "_store_and_activate_script",
                               return_value={FILTER_SECTION_NOTIFICATION}):
            result = client.set_merged_filters(filters_config)

        # Section was skipped by server
        assert result[FILTER_SECTION_NOTIFICATION] is False

    def test_disabled_forward_section_skipped(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_FORWARD: {
                "enabled": 0,
                "forwardAddress": ["fwd@example.com"],
            }
        }

        with mock.patch.object(client, "set_active"):
            with mock.patch.object(client, "_cleanup_scripts"):
                result = client.set_merged_filters(filters_config)

        assert result[FILTER_SECTION_FORWARD] is False

    def test_disabled_vacation_section_skipped(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_VACATION: {
                "enabled": 0,
                "customSubject": "Away",
                "customSubjectEnabled": True,
                "autoReplyText": "Out.",
                "startDate": None, "endDate": None, "timezone": "UTC",
                "startTime": None, "endTime": None, "weekdaysEnabled": False, "days": [],
            }
        }

        with mock.patch.object(client, "set_active"):
            with mock.patch.object(client, "_cleanup_scripts"):
                result = client.set_merged_filters(filters_config)

        assert result[FILTER_SECTION_VACATION] is False

    def test_notification_with_empty_addresses_still_activated(self):
        fake_conn = FakeSieveConnection()
        client = authenticated_client(fake_conn)

        filters_config = {
            FILTER_SECTION_NOTIFICATION: {
                "enabled": 1,
                "notifyAddresses": [],
                "notifyMessage": "",
            }
        }

        with mock.patch.object(client, "set_active"):
            with mock.patch.object(client, "_cleanup_scripts"):
                result = client.set_merged_filters(filters_config)

        # Empty addresses: marked activated for DB persistence but no script added
        assert result[FILTER_SECTION_NOTIFICATION] is True


# ===========================================================================
# Standalone functional tests (flat style, à la test_clientImap)
# ===========================================================================

def test_connect_plain_success():
    """Test successful connection with PLAIN encryption."""
    client = make_client(encryption=cs.SOCKET_ENC_PLAIN)
    with mock.patch("app.manager.mail.ClientSieve.Client") as MockClient:
        MockClient.return_value = FakeSieveConnection()
        client.connect()
    assert client.connected is True


def test_connect_unknown_encryption_raises():
    """Test that connecting with unknown encryption raises BugException."""
    client = make_client(encryption="SUPER_ENCRYPT")
    with pytest.raises(BugException):
        client.connect()


def test_login_success():
    """Test successful login."""
    fake_conn = FakeSieveConnection()
    client = make_client()
    client.connection = fake_conn
    client.connected = True

    client.login("user@example.com", "secret")
    assert client.authenticated is True
    assert fake_conn.logged_in is True


def test_login_no_connection_raises():
    """Test that login without connection raises BugException."""
    client = make_client()
    with pytest.raises(BugException):
        client.login("user@example.com", "secret")


def test_put_script_success():
    """Test putting a script succeeds."""
    fake_conn = FakeSieveConnection()
    client = authenticated_client(fake_conn)

    success, missing = client.put_script("test", "keep;")
    assert success is True
    assert missing is None


def test_delete_script_success():
    """Test deleting an existing script."""
    fake_conn = FakeSieveConnection()
    fake_conn.scripts["to-delete"] = "keep;"
    client = authenticated_client(fake_conn)

    client.delete_script("to-delete")
    assert "to-delete" not in fake_conn.scripts


def test_set_active_success():
    """Test setting a script as active."""
    fake_conn = FakeSieveConnection()
    client = authenticated_client(fake_conn)

    client.set_active("sogo-master")
    assert fake_conn.active_script == "sogo-master"


def test_logout_success():
    """Test successful logout."""
    fake_conn = FakeSieveConnection()
    fake_conn.logged_in = True
    client = authenticated_client(fake_conn)

    client.logout()
    assert fake_conn.logged_in is False
    assert client.authenticated is False
    assert client.connected is False


def test_validate_email_valid():
    """Test email validation with valid address."""
    client = make_client()
    assert client._validate_email("hello@world.com") is True


def test_validate_email_invalid():
    """Test email validation with invalid address."""
    client = make_client()
    assert client._validate_email("notvalid") is False


def test_build_forward_script_keep_copy():
    """Test forward script with keep_copy enabled."""
    client = make_client()
    script = client._build_forward_script(["a@example.com"], keep_copy=1)
    assert "keep" in script
    assert "discard" not in script


def test_build_forward_script_discard():
    """Test forward script without keep_copy discards mail."""
    client = make_client()
    script = client._build_forward_script(["a@example.com"], keep_copy=0)
    assert "discard" in script


def test_build_vacation_script_basic():
    """Test basic vacation script generation."""
    client = make_client()
    config = {
        "enabled": 1,
        "customSubject": "On Holiday",
        "customSubjectEnabled": True,
        "autoReplyText": "I am on holiday.",
        "startDate": None, "endDate": None, "timezone": "UTC",
        "startTime": None, "endTime": None, "weekdaysEnabled": False, "days": [],
    }
    script = client._build_vacation_script(config)
    assert "On Holiday" in script
    assert "I am on holiday" in script


def test_set_merged_filters_empty_config_deactivates():
    """Test that empty filters config deactivates the script."""
    fake_conn = FakeSieveConnection()
    client = authenticated_client(fake_conn)

    with mock.patch.object(client, "set_active") as mock_deactivate:
        with mock.patch.object(client, "_cleanup_scripts"):
            client.set_merged_filters({})

    mock_deactivate.assert_called_once_with("")


def test_set_merged_filters_not_authenticated_raises():
    """Test that set_merged_filters raises BugException when not authenticated."""
    client = make_client()
    client.connection = None
    with pytest.raises(BugException):
        client.set_merged_filters({})
