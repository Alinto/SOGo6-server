"""Unit tests for InterfaceApiCalendarCalendar - shared calendar discovery, subscription and share-time subscribe."""
from unittest.mock import MagicMock

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalCalendarSerializerDict import CalCalendarSerializerDict
from app.module.calendar.serializer.CalCalendarsSerializerList import CalCalendarsSerializerList
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException

_ME = "bob@example.com"
_VIEW_RIGHTS = {"public": "view-all", "confidential": "none", "private": "none",
                "can_create_objects": False, "can_erase_objects": False}
_NO_VIEW_RIGHTS = {"public": "none", "confidential": "none", "private": "none",
                   "can_create_objects": True, "can_erase_objects": False}


def _build_interface(subs=None):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = _ME
    inter.user.mail = _ME
    inter.user.folders = {"CALENDAR": {"OWNER": {"mine": True}, "SUBS": dict(subs or {})}}
    inter.module = MagicMock()
    inter.module.get_all_calendars.return_value = []
    inter.module.get_calendar_share.return_value = []
    inter._calendar_serializer = CalCalendarSerializerDict()
    inter._calendars_serializer = CalCalendarsSerializerList()
    inter._events_serializer = MagicMock(serialize=MagicMock(return_value=[]))
    inter._task_serializer = MagicMock()
    inter._process_setting = MagicMock(SOGO_P_PUBLIC_BASE_URL="")
    inter._user_module = MagicMock()
    inter._share_targets = {}
    # Every uid resolves to itself, "anyone" to the pseudo-user.
    inter._resolve_to_user = lambda entry: cs.ANYONE_TO_USER if entry.get("user_class") == cs.USER_CLASS_ANY else entry["uid"]
    inter._serialize_share_entries = MagicMock(return_value=[])
    return inter


def _cal(key, owner="alice@example.com"):
    return CalCalendar(key=key, user_uid=owner, name=key)


def _subs_added(inter):
    return [c.args for c in inter._user_module.add_folder_key.call_args_list]


# ========== listings only cover subscriptions ==========

def test_get_all_calendars_passes_subscribed_keys_hidden_ones_included():
    inter = _build_interface(subs={"a": True, "b": False})
    inter.get_all_calendars()
    assert inter.module.get_all_calendars.call_args.args[1] == ["a", "b"]


def test_get_all_calendars_without_subs_section_lists_no_shared():
    inter = _build_interface()
    inter.user.folders = {}
    inter.get_all_calendars()
    assert inter.module.get_all_calendars.call_args.args[1] == []


def test_get_events_without_key_restricts_to_subscribed_calendars():
    inter = _build_interface(subs={"a": True})
    inter.module.get_all_events.return_value = []
    inter.get_events(None, {})
    assert inter.module.get_all_events.call_args.args[6] == ["a"]


def test_get_events_with_key_relies_on_acl_only():
    inter = _build_interface(subs={"a": True})
    inter.module.get_all_events.return_value = []
    inter._calendar_user_for = MagicMock()
    inter.get_events("unsubscribed", {})
    assert inter.module.get_all_events.call_args.args[6] is None


def test_get_tasks_without_key_restricts_to_subscribed_calendars():
    inter = _build_interface(subs={"a": True})
    inter.module.get_all_tasks.return_value = []
    inter.get_tasks(None, {})
    assert inter.module.get_all_tasks.call_args.args[5] == ["a"]


# ========== discovery ==========

def test_get_shared_calendars_flags_subscription():
    inter = _build_interface(subs={"a": False})
    inter.module.get_shared_calendars.return_value = [_cal("a"), _cal("b")]
    response, _ = inter.get_shared_calendars()
    assert response["data"]["total_count"] == 2
    assert [(c["key"], c["subscribed"]) for c in response["data"]["calendars"]] == [("a", True), ("b", False)]


# ========== subscribe / unsubscribe ==========

def test_subscribe_adds_key_to_subs():
    inter = _build_interface()
    inter.module.require_subscribable.return_value = _cal("a")
    response, _ = inter.set_calendar_subscription("a", {"subscribe": True})
    assert response["error_code"] == "S000000"
    assert response["data"]["subscribed"] is True
    inter._user_module.add_folder_key.assert_called_once_with(_ME, "CALENDAR", "a", owner_key="SUBS")


def test_subscribe_is_idempotent_and_keeps_display_toggle():
    inter = _build_interface(subs={"a": False})
    inter.module.require_subscribable.return_value = _cal("a")
    response, _ = inter.set_calendar_subscription("a", {"subscribe": True})
    assert response["error_code"] == "S000000"
    inter._user_module.add_folder_key.assert_not_called()


def test_subscribe_refused_writes_nothing():
    inter = _build_interface()
    inter.module.require_subscribable.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    response, _ = inter.set_calendar_subscription("a", {"subscribe": True})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c
    inter._user_module.add_folder_key.assert_not_called()


def test_unsubscribe_removes_key_without_access_check():
    inter = _build_interface(subs={"a": True})
    response, _ = inter.set_calendar_subscription("a", {"subscribe": False})
    assert response["error_code"] == "S000000"
    assert response["data"] == {"key": "a", "subscribed": False}
    inter._user_module.remove_folder_key.assert_called_once_with(_ME, "CALENDAR", "a", owner_key="SUBS")
    inter.module.get_calendar.assert_not_called()
    inter.module.require_subscribable.assert_not_called()


# ========== share-time subscription ==========

def test_patch_share_does_not_subscribe_by_default():
    inter = _build_interface()
    inter.patch_calendar_share("k", [{"uid": "carol@example.com", "user_class": "user", "rights": _VIEW_RIGHTS}])
    inter._user_module.add_folder_key.assert_not_called()


def test_patch_share_subscribes_when_asked():
    inter = _build_interface()
    inter.patch_calendar_share("k", [{"uid": "carol@example.com", "user_class": "user",
                                      "rights": _VIEW_RIGHTS, "subscribe": True}])
    assert _subs_added(inter) == [("carol@example.com", "CALENDAR", "k")]


def test_patch_share_never_subscribes_anyone():
    inter = _build_interface()
    inter.patch_calendar_share("k", [{"user_class": cs.USER_CLASS_ANY, "rights": _VIEW_RIGHTS, "subscribe": True}])
    inter._user_module.add_folder_key.assert_not_called()


def test_patch_share_does_not_subscribe_without_view_right():
    inter = _build_interface()
    inter.patch_calendar_share("k", [{"uid": "carol@example.com", "user_class": "user",
                                      "rights": _NO_VIEW_RIGHTS, "subscribe": True}])
    inter._user_module.add_folder_key.assert_not_called()


def test_put_share_subscribes_only_flagged_users():
    inter = _build_interface()
    inter.put_calendar_share("k", [
        {"uid": "carol@example.com", "user_class": "user", "rights": _VIEW_RIGHTS, "subscribe": True},
        {"uid": "dave@example.com", "user_class": "user", "rights": _VIEW_RIGHTS},
    ])
    assert _subs_added(inter) == [("carol@example.com", "CALENDAR", "k")]


def test_post_share_grants_full_rights_and_honours_subscribe():
    inter = _build_interface()
    inter.post_calendar_share("k", [{"uid": "carol@example.com", "user_class": "user",
                                     "rights": _NO_VIEW_RIGHTS, "subscribe": True}])
    inter.module.grant_calendar_share.assert_called_once_with(inter.user, "k", ["carol@example.com"])
    assert _subs_added(inter) == [("carol@example.com", "CALENDAR", "k")]
