"""Unit tests for shared calendar subscriptions: listing vs access resolution, discovery and subscribe checks."""
from unittest.mock import MagicMock

import pytest

from app.factory.share.RepositoryAcl import AclEntry, RepositoryAcl
from app.factory.share.shareCalendar import FULL_MODIFY_RIGHTS, ShareCalendar
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.acl.CalendarAclEngine import CalendarAclEngine
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.source.CalendarSources import CalendarSources
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException

_ME = "bob@example.com"
_OWNER = "alice@example.com"

_VIEW_RIGHTS = {"public": "view-all", "confidential": "none", "private": "none",
                "can_create_objects": False, "can_erase_objects": False}
_NO_VIEW_RIGHTS = {"public": "none", "confidential": "none", "private": "none",
                   "can_create_objects": True, "can_erase_objects": True}


def _cal(key, owner=_OWNER):
    return CalCalendar(key=key, user_uid=owner, name=key, source_type=CalendarSourceType.LOCAL)


def _entry(key, to_user=_ME, owner=_OWNER, rights=None):
    return AclEntry(resource_type="calendar", key=key, owner=owner, to_user=to_user, rights=rights or _VIEW_RIGHTS)


def _user(uid=_ME):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return user


def _build_sources(owned=(), by_key=None, direct=(), anyone=()):
    """CalendarSources over mocked repositories.

    by_key maps a key to its calendar (find_by_key_only); direct / anyone are the ACL entries
    returned for the user and for the "anyone" pseudo-user of the user's domain.
    """
    by_key = dict(by_key or {})
    sources = object.__new__(CalendarSources)
    sources._db = MagicMock()
    sources._repo_calendar = MagicMock()
    sources._repo_calendar.find_all.return_value = list(owned)
    sources._repo_calendar.find_by_key.return_value = None
    sources._repo_calendar.find_by_key_only.side_effect = by_key.get
    acl: dict[str, AclEntry] = {e.key: e for e in (*direct, *anyone)}
    share = MagicMock()
    share.get_keys_shared_with.return_value = list(direct)
    share.get_keys_shared_with_anyone_in_domain.return_value = list(anyone)
    share.get_user_or_anyone.side_effect = lambda uid, owner, key: acl.get(key)
    sources._share = share
    return sources


# ========== CalendarSources.get_listed ==========

def test_get_listed_returns_owned_and_subscribed_shared():
    sources = _build_sources(owned=[_cal("mine", _ME)], by_key={"shared": _cal("shared")},
                             direct=[_entry("shared")])
    listed = sources.get_listed(_ME, ["shared"])
    assert [s.calendar.key for s in listed] == ["mine", "shared"]


def test_get_listed_skips_unsubscribed_shared():
    sources = _build_sources(owned=[_cal("mine", _ME)], by_key={"shared": _cal("shared")},
                             direct=[_entry("shared")])
    listed = sources.get_listed(_ME, [])
    assert [s.calendar.key for s in listed] == ["mine"]


def test_get_listed_drops_orphan_subscriptions_silently():
    """A subscription whose share was revoked, or whose calendar was deleted, is not listed."""
    sources = _build_sources(by_key={"revoked": _cal("revoked")})
    assert not sources.get_listed(_ME, ["revoked", "deleted"])


def test_get_listed_does_not_duplicate_owned_key():
    sources = _build_sources(owned=[_cal("mine", _ME)])
    listed = sources.get_listed(_ME, ["mine"])
    assert [s.calendar.key for s in listed] == ["mine"]


def test_get_all_still_returns_every_accessible_calendar():
    """Access resolution (event lookup, iMIP) ignores subscriptions."""
    sources = _build_sources(owned=[_cal("mine", _ME)], by_key={"shared": _cal("shared")},
                             direct=[_entry("shared")])
    assert [s.calendar.key for s in sources.get_all(_ME)] == ["mine", "shared"]


def test_get_all_events_with_listed_keys_only_scans_listed_calendars():
    sources = _build_sources()
    listed, everything = MagicMock(), MagicMock()
    listed.get_all_events.return_value = []
    sources.get_listed = MagicMock(return_value=[listed])
    sources.get_all = MagicMock(return_value=[everything])
    sources.get_all_events(_ME, listed_shared_keys=["shared"])
    sources.get_listed.assert_called_once_with(_ME, ["shared"])
    everything.get_all_events.assert_not_called()


def test_get_all_tasks_without_listed_keys_scans_every_calendar():
    sources = _build_sources()
    source = MagicMock()
    source.get_all_tasks.return_value = []
    sources.get_all = MagicMock(return_value=[source])
    sources.get_listed = MagicMock()
    sources.get_all_tasks(_ME)
    sources.get_listed.assert_not_called()
    source.get_all_tasks.assert_called_once()


# ========== CalendarSources.get_shared_calendars ==========

def test_get_shared_calendars_queries_anyone_shares_of_user_domain_only():
    sources = _build_sources()
    sources.get_shared_calendars(_ME)
    sources._share.get_keys_shared_with_anyone_in_domain.assert_called_once_with("example.com")


def test_get_shared_calendars_rechecks_exact_owner_domain():
    """The SQL LIKE is only a prefilter: an owner of another domain is still rejected."""
    other = _cal("other", owner="eve@exampleXcom")
    sources = _build_sources(by_key={"other": other},
                             anyone=[_entry("other", to_user=cs.ANYONE_TO_USER, owner="eve@exampleXcom")])
    assert not sources.get_shared_calendars(_ME)


def test_get_shared_calendars_merges_direct_and_anyone_without_duplicates():
    sources = _build_sources(
        by_key={"a": _cal("a"), "b": _cal("b")},
        direct=[_entry("a")],
        anyone=[_entry("a", to_user=cs.ANYONE_TO_USER), _entry("b", to_user=cs.ANYONE_TO_USER)],
    )
    assert [c.key for c in sources.get_shared_calendars(_ME)] == ["a", "b"]


def test_get_shared_calendars_excludes_own_anyone_share():
    sources = _build_sources(by_key={"mine": _cal("mine", _ME)},
                             anyone=[_entry("mine", to_user=cs.ANYONE_TO_USER, owner=_ME)])
    assert not sources.get_shared_calendars(_ME)


# ========== RepositoryAcl / ShareCalendar ==========

def test_repository_filters_anyone_shares_by_owner_domain_in_sql():
    db = MagicMock()
    db.select_from_table.return_value = []
    RepositoryAcl(db).find_all_for_to_user_by_owner_domain("calendar", cs.ANYONE_TO_USER, "example.com")
    condition = db.select_from_table.call_args.kwargs["condition"]
    assert "LikeCondition(owner LIKE '%@example.com')" in repr(condition)


@pytest.mark.parametrize("rights, expected", [
    (_VIEW_RIGHTS, True),
    (_NO_VIEW_RIGHTS, False),
    ({"public": "none", "confidential": "none", "private": "view-date-time"}, True),
    (FULL_MODIFY_RIGHTS, True),
    ({}, False),
])
def test_grants_view(rights, expected):
    assert ShareCalendar.grants_view(rights) is expected


# ========== ModuleCalendar ==========

def _build_module(sources):
    module = object.__new__(ModuleCalendar)
    module._db = MagicMock()
    module._sources = sources
    module._share = sources._share
    sources._share.to_calendar_permissions = ShareCalendar.to_calendar_permissions
    module._acl = CalendarAclEngine(share=sources._share)
    return module


def test_get_all_calendars_lists_owned_and_subscribed_shared():
    sources = _build_sources(owned=[_cal("mine", _ME)], by_key={"a": _cal("a"), "b": _cal("b")},
                             direct=[_entry("a"), _entry("b")])
    calendars = _build_module(sources).get_all_calendars(_user(), ["b"])
    assert [c.key for c in calendars] == ["mine", "b"]


def test_get_all_calendars_drops_subscription_without_view_right():
    sources = _build_sources(by_key={"a": _cal("a")}, direct=[_entry("a", rights=_NO_VIEW_RIGHTS)])
    assert not _build_module(sources).get_all_calendars(_user(), ["a"])


def test_get_shared_calendars_lists_visible_shares_with_permissions():
    sources = _build_sources(by_key={"a": _cal("a"), "b": _cal("b")},
                             direct=[_entry("a"), _entry("b", rights=_NO_VIEW_RIGHTS)])
    calendars = _build_module(sources).get_shared_calendars(_user())
    assert [c.key for c in calendars] == ["a"]
    assert calendars[0].permissions is not None


def test_get_shared_calendars_includes_anyone_shares():
    sources = _build_sources(by_key={"a": _cal("a")}, anyone=[_entry("a", to_user=cs.ANYONE_TO_USER)])
    assert [c.key for c in _build_module(sources).get_shared_calendars(_user())] == ["a"]


def test_require_subscribable_accepts_anyone_share():
    sources = _build_sources(by_key={"a": _cal("a")}, anyone=[_entry("a", to_user=cs.ANYONE_TO_USER)])
    assert _build_module(sources).require_subscribable(_user(), "a").key == "a"


def test_require_subscribable_refuses_own_calendar():
    sources = _build_sources()
    sources._repo_calendar.find_by_key.return_value = _cal("mine", _ME)
    with pytest.raises(RequestException) as exc:
        _build_module(sources).require_subscribable(_user(), "mine")
    assert exc.value.error == err.ERROR_CALENDAR_CANNOT_SUBSCRIBE_OWN


def test_require_subscribable_hides_calendar_without_view_right():
    sources = _build_sources(by_key={"a": _cal("a")}, direct=[_entry("a", rights=_NO_VIEW_RIGHTS)])
    with pytest.raises(RequestException) as exc:
        _build_module(sources).require_subscribable(_user(), "a")
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_require_subscribable_refuses_unshared_calendar():
    sources = _build_sources(by_key={"a": _cal("a")})
    with pytest.raises(RequestException) as exc:
        _build_module(sources).require_subscribable(_user(), "a")
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND
