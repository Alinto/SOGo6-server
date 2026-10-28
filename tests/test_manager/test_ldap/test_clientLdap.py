"""
Unit tests for ClientLdap (pytest).

The LDAP server is never contacted: `ldap.initialize` is monkeypatched and the
connection object is a MagicMock. The real `ldap` module is still used for
exceptions, constants and filter escaping.

Assumption: the module under test lives at app.manager.user_source.ClientLdap.
Adjust MODULE_PATH / the import below if it is located elsewhere.
"""
from __future__ import annotations

import base64
from datetime import datetime
from unittest.mock import MagicMock, patch

import ldap
import pytest

import app.manager.ldap.ClientLdap as mod
from app.manager.ldap.ClientLdap import (
    ClientLdap,
    condition_to_filter,
    ldap_escape,
    parse_python_ldap_record,
)
from app.utils import constants as cs
from app.utils import exceptions as exc
from app.utils.db import Condition


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #

def make_client(**overrides) -> ClientLdap:
    params = dict(
        ldap_host="ldap.example.org",
        ldap_port=389,
        ldap_enc="none",
        ldap_bind_dn="cn=admin,dc=example,dc=org",
        ldap_bind_pwd="secret",
        ldap_base_dn="ou=users,dc=example,dc=org",
        ldap_scope=cs.LDAP_SCOPE_SUB,
        ldap_uid="uid",
        ldap_id="uid",
        ldap_cn="cn",
        ldap_mails=["mail", "alias"],
    )
    params.update(overrides)
    return ClientLdap(**params)


@pytest.fixture
def client() -> ClientLdap:
    c = make_client()
    c.ldap_conn = MagicMock()
    c.connected = True
    return c


@pytest.fixture
def disconnected_client() -> ClientLdap:
    c = make_client()
    c.ldap_conn = None
    c.connected = False
    return c


# --------------------------------------------------------------------------- #
# ldap_escape
# --------------------------------------------------------------------------- #

class TestLdapEscape:
    def test_int_is_returned_unchanged(self):
        assert ldap_escape(42) == 42

    def test_datetime_becomes_timestamp(self):
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert ldap_escape(dt) == int(dt.timestamp())

    def test_plain_string_unchanged(self):
        assert ldap_escape("john") == "john"

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("a(b", r"a\28b"),
            ("a)b", r"a\29b"),
            ("a\\b", r"a\5cb"),
            ("a*b", r"a\2ab"),
        ],
    )
    def test_special_chars_are_escaped(self, raw, expected):
        assert ldap_escape(raw) == expected

    def test_wildcard_kept_when_requested(self):
        assert ldap_escape("jo*", with_wildcard=True) == "jo*"

    def test_other_special_chars_still_escaped_with_wildcard(self):
        assert ldap_escape("*)(uid=*", with_wildcard=True) == r"*\29\28uid=*"

    def test_injection_attempt_is_neutralised(self):
        escaped = ldap_escape("admin)(|(uid=*")
        assert "(" not in escaped and ")" not in escaped


# --------------------------------------------------------------------------- #
# condition_to_filter
# --------------------------------------------------------------------------- #

class TestConditionToFilter:
    def test_equal(self):
        assert condition_to_filter(Condition.EqualCondition("cn", "john")) == "(cn=john)"

    def test_like(self):
        assert condition_to_filter(Condition.LikeCondition("cn", "jo*")) == "(cn=jo*)"

    def test_not_equal(self):
        assert condition_to_filter(Condition.NotEqualCondition("cn", "john")) == "(cn!=john)"

    def test_not_like(self):
        assert condition_to_filter(Condition.NotLikeCondition("cn", "jo*")) == "(cn!=jo*)"

    def test_true(self):
        assert condition_to_filter(Condition.TrueCondition()) == "(objectClass=*)"

    def test_less_or_equal(self):
        assert condition_to_filter(Condition.LessOrEqualCondition("age", 10)) == "(age<=10)"

    def test_greater_or_equal(self):
        assert condition_to_filter(Condition.GreaterOrEqualCondition("age", 10)) == "(age>=10)"

    def test_and(self):
        cond = Condition.AndCondition(
            Condition.EqualCondition("a", "1"),
            Condition.EqualCondition("b", "2"),
        )
        assert condition_to_filter(cond) == "(&(a=1)(b=2))"

    def test_or(self):
        cond = Condition.OrCondition(
            Condition.EqualCondition("a", "1"),
            Condition.EqualCondition("b", "2"),
        )
        assert condition_to_filter(cond) == "(|(a=1)(b=2))"

    def test_nested(self):
        cond = Condition.AndCondition(
            Condition.OrCondition(
                Condition.EqualCondition("a", "1"),
                Condition.EqualCondition("b", "2"),
            ),
            Condition.NotEqualCondition("c", "3"),
        )
        assert condition_to_filter(cond) == "(&(|(a=1)(b=2))(c!=3))"

    def test_value_is_escaped(self):
        result = condition_to_filter(Condition.EqualCondition("cn", "a)(b"))
        assert result == r"(cn=a\29\28b)"

    def test_unknown_condition_raises_bug(self):
        with pytest.raises(exc.BugException):
            condition_to_filter(object())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# parse_python_ldap_record
# --------------------------------------------------------------------------- #

class TestParseRecord:
    def test_decodes_and_adds_dn(self):
        record = ("uid=john,dc=x", {"cn": [b"John", b"Johnny"], "uid": [b"john"]})
        assert parse_python_ldap_record(record) == {
            "cn": ["John", "Johnny"],
            "uid": ["john"],
            "dn": ["uid=john,dc=x"],
        }

    def test_binary_values_are_base64(self):
        raw = b"\xff\xfe\x00"
        record = ("uid=john,dc=x", {"jpegPhoto": [raw]})
        result = parse_python_ldap_record(record)
        assert result["jpegPhoto"] == [base64.b64encode(raw).decode()]

    def test_password_removed_by_default(self):
        record = ("dn", {"password": [b"x"], "cn": [b"John"]})
        assert "password" not in parse_python_ldap_record(record)

    def test_password_kept_when_requested(self):
        record = ("dn", {"password": [b"x"]})
        assert parse_python_ldap_record(record, pop_password=False)["password"] == ["x"]

    def test_empty_attributes(self):
        assert parse_python_ldap_record(("dn", {})) == {"dn": ["dn"]}


# --------------------------------------------------------------------------- #
# __init__
# --------------------------------------------------------------------------- #

class TestInit:
    @pytest.mark.parametrize(
        "scope_cs, scope_ldap",
        [
            (cs.LDAP_SCOPE_BASE, ldap.SCOPE_BASE),
            (cs.LDAP_SCOPE_ONE, ldap.SCOPE_ONELEVEL),
            (cs.LDAP_SCOPE_SUB, ldap.SCOPE_SUBTREE),
        ],
    )
    def test_scope_mapping(self, scope_cs, scope_ldap):
        assert make_client(ldap_scope=scope_cs).scope == scope_ldap

    def test_main_mail_is_first(self):
        assert make_client().ldap_main_mail == "mail"

    def test_filter_none_by_default(self):
        assert make_client().filter is None

    def test_filter_is_converted(self):
        c = make_client(ldap_filter=Condition.EqualCondition("objectClass", "person"))
        assert c.filter == "(objectClass=person)"

    def test_initial_state(self):
        c = make_client()
        assert c.binded is False
        assert c.ldap_conn is None


# --------------------------------------------------------------------------- #
# connect
# --------------------------------------------------------------------------- #

class TestConnect:
    def test_plain_connection(self, monkeypatch):
        init = MagicMock()
        monkeypatch.setattr(mod.ldap, "initialize", init)
        c = make_client(ldap_enc="none")
        c.connect()
        assert init.call_args.args[0] == "ldap://ldap.example.org:389"
        assert c.connected is True
        assert c.ldap_conn.protocol_version == ldap.VERSION3
        c.ldap_conn.start_tls_s.assert_not_called()

    def test_implicit_tls_uses_ldaps(self, monkeypatch):
        init = MagicMock()
        set_option = MagicMock()
        monkeypatch.setattr(mod.ldap, "initialize", init)
        monkeypatch.setattr(mod.ldap, "set_option", set_option)
        c = make_client(ldap_enc=cs.SOCKET_ENC_IMPLICIT_TLS, ldap_port=636)
        c.connect()
        assert init.call_args.args[0] == "ldaps://ldap.example.org:636"

    def test_implicit_tls_trusted_cert_and_ca(self, monkeypatch):
        monkeypatch.setattr(mod.ldap, "initialize", MagicMock())
        set_option = MagicMock()
        monkeypatch.setattr(mod.ldap, "set_option", set_option)
        c = make_client(
            ldap_enc=cs.SOCKET_ENC_IMPLICIT_TLS,
            ldap_check_cert=cs.CERT_TRUSTED,
            ldap_ca_path="/tmp/ca.pem",
        )
        c.connect()
        set_option.assert_any_call(ldap.OPT_X_TLS_CACERTFILE, "/tmp/ca.pem")
        set_option.assert_any_call(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)

    def test_implicit_tls_no_cert_check(self, monkeypatch):
        monkeypatch.setattr(mod.ldap, "initialize", MagicMock())
        set_option = MagicMock()
        monkeypatch.setattr(mod.ldap, "set_option", set_option)
        c = make_client(ldap_enc=cs.SOCKET_ENC_IMPLICIT_TLS, ldap_check_cert=cs.CERT_NONE)
        c.connect()
        set_option.assert_any_call(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

    def test_implicit_tls_legacy_does_not_touch_cert_option(self, monkeypatch):
        monkeypatch.setattr(mod.ldap, "initialize", MagicMock())
        set_option = MagicMock()
        monkeypatch.setattr(mod.ldap, "set_option", set_option)
        c = make_client(ldap_enc=cs.SOCKET_ENC_IMPLICIT_TLS, ldap_check_cert=cs.CERT_LEGACY)
        c.connect()
        set_option.assert_not_called()

    def test_explicit_tls_calls_start_tls(self, monkeypatch):
        init = MagicMock()
        monkeypatch.setattr(mod.ldap, "initialize", init)
        c = make_client(ldap_enc=cs.SOCKET_ENC_EXPLICIT_TLS)
        c.connect()
        assert init.call_args.args[0].startswith("ldap://")
        init.return_value.start_tls_s.assert_called_once()

    def test_initialize_error_raises_request_exception(self, monkeypatch):
        monkeypatch.setattr(mod.ldap, "initialize", MagicMock(side_effect=ldap.LDAPError("boom")))
        c = make_client()
        with pytest.raises(exc.RequestException):
            c.connect()
        assert c.connected is not True


# --------------------------------------------------------------------------- #
# _bind
# --------------------------------------------------------------------------- #

class TestBind:
    def test_success(self, client):
        client.ldap_conn.simple_bind_s.return_value = (97, [])
        ok, ret = client._bind("cn=admin,dc=example,dc=org", "pwd")
        assert ok is True
        assert ret == (97, [])
        assert client.binded is True
        assert client.ldap_conn.simple_bind_s.call_args.args[0] == "cn=admin,dc=example,dc=org"

    def test_invalid_dn_raises(self, client):
        with pytest.raises(exc.RequestException):
            client._bind("not a dn", "pwd")
        client.ldap_conn.simple_bind_s.assert_not_called()

    def test_invalid_credentials_raises_by_default(self, client):
        client.ldap_conn.simple_bind_s.side_effect = ldap.INVALID_CREDENTIALS
        with pytest.raises(exc.RequestException):
            client._bind("uid=john,dc=x", "bad")

    def test_invalid_credentials_no_throw(self, client):
        client.ldap_conn.simple_bind_s.side_effect = ldap.INVALID_CREDENTIALS
        assert client._bind("uid=john,dc=x", "bad", throw_error=False) == (False, {})
        assert client.binded is False

    def test_other_ldap_error_always_raises(self, client):
        client.ldap_conn.simple_bind_s.side_effect = ldap.SERVER_DOWN
        with pytest.raises(exc.RequestException):
            client._bind("uid=john,dc=x", "pwd", throw_error=False)

    def test_ppolicy_control_added_for_user_bind(self, client):
        client.pwd_policy = True
        client._bind("uid=john,dc=x", "pwd", use_admin=False)
        ctrls = client.ldap_conn.simple_bind_s.call_args.kwargs["serverctrls"]
        assert ctrls is not None and len(ctrls) == 1

    def test_no_ppolicy_control_for_admin_bind(self, client):
        client.pwd_policy = True
        client._bind("cn=admin,dc=x", "pwd", use_admin=True)
        assert client.ldap_conn.simple_bind_s.call_args.kwargs["serverctrls"] is None

    def test_no_ppolicy_control_when_disabled(self, client):
        client._bind("uid=john,dc=x", "pwd", use_admin=False)
        assert client.ldap_conn.simple_bind_s.call_args.kwargs["serverctrls"] is None

    def test_no_connection_raises_bug(self, disconnected_client):
        with pytest.raises(exc.BugException):
            disconnected_client._bind("uid=john,dc=x", "pwd")


# --------------------------------------------------------------------------- #
# _get_dn_for_user
# --------------------------------------------------------------------------- #

class TestGetDnForUser:
    def test_builds_dn_from_id_field(self, client):
        assert client._get_dn_for_user("john", "example.org") == "uid=john,ou=users,dc=example,dc=org"

    def test_username_is_escaped(self, client):
        dn = client._get_dn_for_user("jo*hn", "example.org")
        assert dn.startswith(r"uid=jo\2ahn,")

    def test_domain_placeholder_replaced(self, client):
        client.base_dn = "ou=%d,dc=example,dc=org"
        assert client._get_dn_for_user("john", "sales") == "uid=john,ou=sales,dc=example,dc=org"

    def test_bind_fields_search_dn(self, client):
        client.bind_fields = ["mail"]
        with patch.object(client, "_bind", return_value=(True, None)) as bind, \
             patch.object(client, "_search_dn", return_value="uid=found,dc=x") as search:
            result = client._get_dn_for_user("john@example.org", "example.org")
        assert result == "uid=found,dc=x"
        bind.assert_called_once_with(client.bind_dn, client.bind_pwd, use_admin=True)
        search.assert_called_once_with("ou=users,dc=example,dc=org", "(mail=john@example.org)")

    def test_bind_fields_multiple_use_or(self, client):
        client.bind_fields = ["mail", "uid"]
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_dn", return_value="x") as search:
            client._get_dn_for_user("john", "example.org")
        assert search.call_args.args[1] == "(|(mail=john)(uid=john))"

    def test_bind_fields_with_extra_filter(self, client):
        client.bind_fields = ["mail"]
        client.filter = "(objectClass=person)"
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_dn", return_value="x") as search:
            client._get_dn_for_user("john", "example.org")
        assert search.call_args.args[1] == "(&(mail=john)(objectClass=person))"

    def test_not_connected_raises_bug(self, disconnected_client):
        with pytest.raises(exc.BugException):
            disconnected_client._get_dn_for_user("john", "example.org")


# --------------------------------------------------------------------------- #
# check_login
# --------------------------------------------------------------------------- #

class TestCheckLogin:
    USER_DN = "uid=john,ou=users,dc=example,dc=org"
    RECORD = (USER_DN, {"uid": [b"john"], "cn": [b"John"]})

    def test_success(self, client):
        with patch.object(client, "_get_dn_for_user", return_value=self.USER_DN), \
             patch.object(client, "_bind", return_value=(True, {})) as bind, \
             patch.object(client, "_search_small", return_value=[self.RECORD]) as search:
            ok, extra, contact = client.check_login("john", "pwd", "example.org")
        assert ok is True
        assert extra == {}
        assert contact == {"uid": ["john"], "cn": ["John"], "dn": [self.USER_DN]}
        # user bind, then rebind as admin
        assert bind.call_count == 2
        search.assert_called_once_with(self.USER_DN, client.filter)

    def test_bind_as_user_does_not_rebind_as_admin(self, client):
        client.bind_as_user = True
        with patch.object(client, "_get_dn_for_user", return_value=self.USER_DN), \
             patch.object(client, "_bind", return_value=(True, {})) as bind, \
             patch.object(client, "_search_small", return_value=[self.RECORD]):
            client.check_login("john", "pwd", "example.org")
        assert bind.call_count == 1

    def test_no_dn_found(self, client):
        with patch.object(client, "_get_dn_for_user", return_value=""):
            assert client.check_login("john", "pwd", "example.org") == (False, {}, {})

    def test_wrong_password(self, client):
        with patch.object(client, "_get_dn_for_user", return_value=self.USER_DN), \
             patch.object(client, "_bind", return_value=(False, {})), \
             patch.object(client, "_search_small") as search:
            assert client.check_login("john", "bad", "example.org") == (False, {}, {})
        search.assert_not_called()

    def test_bind_ok_but_search_empty_raises_bug(self, client):
        with patch.object(client, "_get_dn_for_user", return_value=self.USER_DN), \
             patch.object(client, "_bind", return_value=(True, {})), \
             patch.object(client, "_search_small", return_value=[]):
            with pytest.raises(exc.BugException):
                client.check_login("john", "pwd", "example.org")

    def test_multiple_results_raises(self, client):
        with patch.object(client, "_get_dn_for_user", return_value=self.USER_DN), \
             patch.object(client, "_bind", return_value=(True, {})), \
             patch.object(client, "_search_small", return_value=[self.RECORD, self.RECORD]):
            with pytest.raises(exc.AggravatedException):
                client.check_login("john", "pwd", "example.org")

    def test_password_attribute_not_returned(self, client):
        record = (self.USER_DN, {"password": [b"hash"], "uid": [b"john"]})
        with patch.object(client, "_get_dn_for_user", return_value=self.USER_DN), \
             patch.object(client, "_bind", return_value=(True, {})), \
             patch.object(client, "_search_small", return_value=[record]):
            _, _, contact = client.check_login("john", "pwd", "example.org")
        assert "password" not in contact


# --------------------------------------------------------------------------- #
# _search_dn / _search_small / _search_big
# --------------------------------------------------------------------------- #

class TestSearchDn:
    def test_returns_first_dn(self, client):
        client.ldap_conn.search_s.return_value = [("uid=a,dc=x", {}), ("uid=b,dc=x", {})]
        assert client._search_dn("dc=x", "(uid=a)") == "uid=a,dc=x"
        client.ldap_conn.search_s.assert_called_once_with(
            "dc=x", client.scope, filterstr="(uid=a)", attrlist=["dn"]
        )

    def test_returns_empty_string_when_nothing_found(self, client):
        client.ldap_conn.search_s.return_value = []
        assert client._search_dn("dc=x", "(uid=a)") == ""

    def test_not_connected_raises_bug(self, disconnected_client):
        with pytest.raises(exc.BugException):
            disconnected_client._search_dn("dc=x", "(uid=a)")


class TestSearchSmall:
    def test_returns_records(self, client):
        records = [("dn", {"cn": [b"x"]})]
        client.ldap_conn.search_s.return_value = records
        assert client._search_small("dc=x", "(cn=x)", ["cn"]) == records
        client.ldap_conn.search_s.assert_called_once_with(
            "dc=x", client.scope, filterstr="(cn=x)", attrlist=["cn"]
        )

    def test_no_such_object_returns_empty(self, client):
        client.ldap_conn.search_s.side_effect = ldap.NO_SUCH_OBJECT
        assert client._search_small("dc=x") == []

    def test_ldap_error_raises_request_exception(self, client):
        client.ldap_conn.search_s.side_effect = ldap.LDAPError("fail")
        with pytest.raises(exc.RequestException):
            client._search_small("dc=x")

    def test_not_connected_raises_bug(self, disconnected_client):
        with pytest.raises(exc.BugException):
            disconnected_client._search_small("dc=x")


class TestSearchBig:
    def test_passes_timeout_and_limit(self, client):
        client.ldap_conn.search_ext_s.return_value = []
        client._search_big("dc=x", "(cn=x)", ["cn"], timeout=5, limit=7)
        client.ldap_conn.search_ext_s.assert_called_once_with(
            "dc=x", client.scope, filterstr="(cn=x)", attrlist=["cn"], timeout=5, sizelimit=7
        )

    def test_default_timeout_and_limit(self, client):
        client.ldap_conn.search_ext_s.return_value = []
        client._search_big("dc=x")
        kwargs = client.ldap_conn.search_ext_s.call_args.kwargs
        assert kwargs["timeout"] == 10
        assert kwargs["sizelimit"] == 100

    def test_no_such_object_returns_empty(self, client):
        client.ldap_conn.search_ext_s.side_effect = ldap.NO_SUCH_OBJECT
        assert client._search_big("dc=x") == []

    def test_ldap_error_raises_request_exception(self, client):
        client.ldap_conn.search_ext_s.side_effect = ldap.LDAPError("fail")
        with pytest.raises(exc.RequestException):
            client._search_big("dc=x")

    def test_not_connected_raises_bug(self, disconnected_client):
        with pytest.raises(exc.BugException):
            disconnected_client._search_big("dc=x")


# --------------------------------------------------------------------------- #
# search_user
# --------------------------------------------------------------------------- #

def _records(n: int):
    return [(f"uid=u{i},dc=x", {"uid": [f"u{i}".encode()]}) for i in range(1, n + 1)]


class TestSearchUser:
    def _call(self, client, **kw):
        args = dict(
            search="u",
            extra_condition=Condition.TrueCondition(),
            limit=10,
            offset=0,
            sort="uid",
            order="asc",
            username="john",
            domain="example.org",
            password="pwd",
        )
        args.update(kw)
        return list(client.search_user(**args))

    def test_first_item_is_total(self, client):
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=_records(3)):
            result = self._call(client)
        assert result[0] == {"total": 3}
        assert [r["uid"] for r in result[1:]] == [["u1"], ["u2"], ["u3"]]

    def test_pagination_limit_and_offset(self, client):
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=_records(5)):
            result = self._call(client, limit=2, offset=1)
        assert result[0] == {"total": 5}
        assert [r["uid"] for r in result[1:]] == [["u2"], ["u3"]]

    def test_offset_beyond_results(self, client):
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=_records(2)):
            result = self._call(client, limit=5, offset=10)
        assert result == [{"total": 2}]

    def test_admin_bind_used_by_default(self, client):
        with patch.object(client, "_bind", return_value=(True, None)) as bind, \
             patch.object(client, "_search_big", return_value=[]):
            self._call(client)
        bind.assert_called_once_with(client.bind_dn, client.bind_pwd, use_admin=True)

    def test_bind_as_user(self, client):
        client.bind_as_user = True
        with patch.object(client, "_get_dn_for_user", return_value="uid=john,dc=x"), \
             patch.object(client, "_bind", return_value=(True, None)) as bind, \
             patch.object(client, "_search_big", return_value=[]):
            self._call(client)
        bind.assert_called_once_with("uid=john,dc=x", "pwd")

    def test_bind_as_user_without_dn_raises(self, client):
        client.bind_as_user = True
        with patch.object(client, "_get_dn_for_user", return_value=""):
            with pytest.raises(exc.RequestException):
                self._call(client)

    def test_failed_bind_yields_zero_total(self, client):
        with patch.object(client, "_bind", return_value=(False, None)), \
             patch.object(client, "_search_big") as search:
            result = self._call(client)
        assert result == [{"total": 0}]
        search.assert_not_called()

    def test_extra_filter_is_combined(self, client):
        client.filter = "(objectClass=person)"
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=[]) as search:
            self._call(client, extra_condition=Condition.EqualCondition("cn", "x"))
        assert search.call_args.args[1] == "(&(cn=x)(objectClass=person))"

    def test_domain_placeholder_in_base_dn(self, client):
        client.base_dn = "ou=%d,dc=x"
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=[]) as search:
            self._call(client, domain="sales")
        assert search.call_args.args[0] == "ou=sales,dc=x"


# --------------------------------------------------------------------------- #
# get_user_info
# --------------------------------------------------------------------------- #

class TestGetUserInfo:
    def _call(self, client):
        return client.get_user_info(
            uid="john",
            extra_condition=Condition.EqualCondition("uid", "john"),
            username="john",
            domain="example.org",
            password="pwd",
        )

    def test_single_result(self, client):
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=_records(1)):
            assert self._call(client) == {"uid": ["u1"], "dn": ["uid=u1,dc=x"]}

    def test_no_result_returns_empty_dict(self, client):
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=[]):
            assert self._call(client) == {}

    def test_failed_bind_returns_empty_dict(self, client):
        with patch.object(client, "_bind", return_value=(False, None)), \
             patch.object(client, "_search_big") as search:
            assert self._call(client) == {}
        search.assert_not_called()

    def test_bind_as_user_without_dn_raises(self, client):
        client.bind_as_user = True
        with patch.object(client, "_get_dn_for_user", return_value=""):
            with pytest.raises(exc.RequestException):
                self._call(client)

    def test_filter_combination(self, client):
        client.filter = "(objectClass=person)"
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=[]) as search:
            self._call(client)
        assert search.call_args.args[1] == "(&(uid=john)(objectClass=person))"

    def test_multiple_results_raises(self, client):
        with patch.object(client, "_bind", return_value=(True, None)), \
             patch.object(client, "_search_big", return_value=_records(2)):
            with pytest.raises(exc.AggravatedException):
                self._call(client)


# --------------------------------------------------------------------------- #
# close
# --------------------------------------------------------------------------- #

class TestClose:
    def test_unbinds_when_bound(self, client):
        client.binded = True
        client.close()
        client.ldap_conn.unbind_s.assert_called_once()

    def test_does_nothing_when_not_bound(self, client):
        client.binded = False
        client.close()
        client.ldap_conn.unbind_s.assert_not_called()

    def test_does_nothing_without_connection(self, disconnected_client):
        disconnected_client.binded = True
        disconnected_client.close()  # must not raise