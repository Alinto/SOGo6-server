"""Unit tests for CalendarAclEngine."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.acl.CalendarAclEngine import CalendarAclEngine
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.model.CalendarUser import CalendarUser
from app.module.calendar.model.enums.CalendarPermissionAction import CalendarPermissionAction
from app.module.calendar.model.enums.CalendarShareLevel import CalendarShareLevel
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_user(uid):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return user


def _make_calendar_user(uid="user@example.com", owner_uid=None):
    user = _make_user(uid)
    owner = _make_user(owner_uid) if owner_uid and owner_uid != uid else user
    return CalendarUser(user=user, owner=owner)


def _make_event(visibility=EventVisibility.PUBLIC, **kwargs):
    defaults = dict(
        uid="evt@test", title="Meeting", description="Notes", location="Room A",
        date_start=_dt(2026, 6, 1, 10), date_end=_dt(2026, 6, 1, 11),
        visibility=visibility,
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _make_cal(source_type=CalendarSourceType.LOCAL):
    return CalCalendar(user_uid="owner@test", name="Test", key="cal-key", source_type=source_type)


def _perms(public=CalendarShareLevel.NONE, confidential=CalendarShareLevel.NONE,
           private=CalendarShareLevel.NONE, can_create=False, can_delete=False):
    return CalendarPermissions(
        public_level=public, confidential_level=confidential,
        private_level=private, can_create=can_create, can_delete=can_delete,
    )


# ========== get_permissions (stub) ==========

def test_owner_gets_full_permissions():
    engine = CalendarAclEngine()
    perms = engine.get_permissions(_make_cal(), _make_calendar_user("alice@test"))
    assert perms.public_level == CalendarShareLevel.MODIFY
    assert perms.confidential_level == CalendarShareLevel.MODIFY
    assert perms.private_level == CalendarShareLevel.MODIFY
    assert perms.can_create is True
    assert perms.can_delete is True


def test_non_owner_gets_denied():
    engine = CalendarAclEngine()
    perms = engine.get_permissions(_make_cal(), _make_calendar_user("bob@test", owner_uid="alice@test"))
    assert perms.public_level == CalendarShareLevel.NONE
    assert perms.can_create is False
    assert perms.can_delete is False


def test_ics_calendar_is_read_only():
    engine = CalendarAclEngine()
    perms = engine.get_permissions(_make_cal(CalendarSourceType.ICS), _make_calendar_user("alice@test"))
    assert perms.public_level == CalendarShareLevel.VIEW_ALL
    assert perms.can_create is False
    assert perms.can_delete is False


# ========== check_permission — VIEW ==========

def test_check_view_allowed_with_view_datetime():
    engine = CalendarAclEngine()
    engine.check_permission(_perms(public=CalendarShareLevel.VIEW_DATETIME), CalendarPermissionAction.VIEW)


def test_check_view_allowed_with_view_all():
    engine = CalendarAclEngine()
    engine.check_permission(_perms(private=CalendarShareLevel.VIEW_ALL), CalendarPermissionAction.VIEW)


def test_check_view_denied_with_all_none():
    engine = CalendarAclEngine()
    with pytest.raises(RequestException):
        engine.check_permission(_perms(), CalendarPermissionAction.VIEW)


def test_check_view_allowed_if_any_class_sufficient():
    engine = CalendarAclEngine()
    engine.check_permission(
        _perms(public=CalendarShareLevel.NONE, confidential=CalendarShareLevel.VIEW_DATETIME),
        CalendarPermissionAction.VIEW,
    )


# ========== check_permission — RESPOND ==========

def test_check_respond_allowed():
    engine = CalendarAclEngine()
    engine.check_permission(_perms(public=CalendarShareLevel.RESPOND), CalendarPermissionAction.RESPOND)


def test_check_respond_denied_with_view_all():
    engine = CalendarAclEngine()
    with pytest.raises(RequestException):
        engine.check_permission(_perms(public=CalendarShareLevel.VIEW_ALL), CalendarPermissionAction.RESPOND)


def test_check_respond_denied_with_view_datetime():
    engine = CalendarAclEngine()
    with pytest.raises(RequestException):
        engine.check_permission(_perms(public=CalendarShareLevel.VIEW_DATETIME), CalendarPermissionAction.RESPOND)


# ========== check_permission — MODIFY ==========

def test_check_modify_allowed():
    engine = CalendarAclEngine()
    engine.check_permission(_perms(public=CalendarShareLevel.MODIFY), CalendarPermissionAction.MODIFY)


def test_check_modify_denied_with_respond():
    engine = CalendarAclEngine()
    with pytest.raises(RequestException):
        engine.check_permission(_perms(public=CalendarShareLevel.RESPOND), CalendarPermissionAction.MODIFY)


def test_check_modify_allowed_on_confidential_only():
    engine = CalendarAclEngine()
    engine.check_permission(
        _perms(public=CalendarShareLevel.NONE, confidential=CalendarShareLevel.MODIFY),
        CalendarPermissionAction.MODIFY,
    )


# ========== check_permission — CREATE / DELETE ==========

def test_check_create_allowed():
    engine = CalendarAclEngine()
    engine.check_permission(_perms(can_create=True), CalendarPermissionAction.CREATE)


def test_check_create_denied():
    engine = CalendarAclEngine()
    with pytest.raises(RequestException):
        engine.check_permission(_perms(can_create=False), CalendarPermissionAction.CREATE)


def test_check_delete_allowed():
    engine = CalendarAclEngine()
    engine.check_permission(_perms(can_delete=True), CalendarPermissionAction.DELETE)


def test_check_delete_denied():
    engine = CalendarAclEngine()
    with pytest.raises(RequestException):
        engine.check_permission(_perms(can_delete=False), CalendarPermissionAction.DELETE)


# ========== check_permission — owner shortcut ==========

def test_owner_passes_all_checks():
    engine = CalendarAclEngine()
    perms = CalendarPermissions.owner()
    for action in CalendarPermissionAction:
        engine.check_permission(perms, action)


def test_denied_fails_all_checks():
    engine = CalendarAclEngine()
    perms = CalendarPermissions.denied()
    for action in CalendarPermissionAction:
        with pytest.raises(RequestException):
            engine.check_permission(perms, action)


# ========== sanitize_events — exclusion (NONE) ==========

def test_sanitize_excludes_events_with_none_level():
    engine = CalendarAclEngine()
    events = [_make_event(EventVisibility.PRIVATE)]
    result = engine.sanitize_events(events, _perms(public=CalendarShareLevel.VIEW_ALL, private=CalendarShareLevel.NONE))
    assert len(result) == 0


def test_sanitize_keeps_public_excludes_private():
    engine = CalendarAclEngine()
    pub = _make_event(EventVisibility.PUBLIC, uid="pub")
    priv = _make_event(EventVisibility.PRIVATE, uid="priv")
    result = engine.sanitize_events(
        [pub, priv],
        _perms(public=CalendarShareLevel.VIEW_ALL, private=CalendarShareLevel.NONE),
    )
    assert len(result) == 1
    assert result[0].uid == "pub"


# ========== sanitize_events — masking (VIEW_DATETIME) ==========

def test_sanitize_masks_event_with_view_datetime():
    engine = CalendarAclEngine()
    event = _make_event(EventVisibility.PUBLIC, title="Secret Meeting", description="Agenda", location="Room B")
    result = engine.sanitize_events([event], _perms(public=CalendarShareLevel.VIEW_DATETIME))
    assert len(result) == 1
    masked = result[0]
    assert masked.title == "Busy"
    assert masked.description is None
    assert masked.location is None
    assert masked.attendees == []
    assert masked.organizer is None
    assert masked.reminders == []
    assert masked.categories == []
    assert masked.url is None
    assert masked.date_start == event.date_start
    assert masked.date_end == event.date_end


def test_sanitize_mask_does_not_mutate_original():
    engine = CalendarAclEngine()
    event = _make_event(EventVisibility.PUBLIC, title="Original")
    engine.sanitize_events([event], _perms(public=CalendarShareLevel.VIEW_DATETIME))
    assert event.title == "Original"


# ========== sanitize_events — full visibility (VIEW_ALL+) ==========

def test_sanitize_preserves_event_with_view_all():
    engine = CalendarAclEngine()
    event = _make_event(EventVisibility.PUBLIC, title="Visible")
    result = engine.sanitize_events([event], _perms(public=CalendarShareLevel.VIEW_ALL))
    assert result[0].title == "Visible"
    assert result[0].description == "Notes"


def test_sanitize_preserves_event_with_respond():
    engine = CalendarAclEngine()
    event = _make_event(EventVisibility.CONFIDENTIAL, title="Conf Meeting")
    result = engine.sanitize_events([event], _perms(confidential=CalendarShareLevel.RESPOND))
    assert result[0].title == "Conf Meeting"


def test_sanitize_preserves_event_with_modify():
    engine = CalendarAclEngine()
    event = _make_event(EventVisibility.PRIVATE, title="Private Note")
    result = engine.sanitize_events([event], _perms(private=CalendarShareLevel.MODIFY))
    assert result[0].title == "Private Note"


# ========== sanitize_events — mixed visibility classes ==========

def test_sanitize_mixed_visibility():
    engine = CalendarAclEngine()
    pub = _make_event(EventVisibility.PUBLIC, uid="pub", title="Public Event")
    conf = _make_event(EventVisibility.CONFIDENTIAL, uid="conf", title="Conf Event")
    priv = _make_event(EventVisibility.PRIVATE, uid="priv", title="Private Event")

    perms = _perms(
        public=CalendarShareLevel.VIEW_ALL,
        confidential=CalendarShareLevel.VIEW_DATETIME,
        private=CalendarShareLevel.NONE,
    )
    result = engine.sanitize_events([pub, conf, priv], perms)

    assert len(result) == 2
    assert result[0].uid == "pub"
    assert result[0].title == "Public Event"
    assert result[1].uid == "conf"
    assert result[1].title == "Busy"


# ========== sanitize_events — empty list ==========

def test_sanitize_empty_list():
    engine = CalendarAclEngine()
    assert engine.sanitize_events([], CalendarPermissions.owner()) == []


# ========== CalendarShareLevel ordering ==========

def test_share_level_ordering():
    assert CalendarShareLevel.NONE < CalendarShareLevel.VIEW_DATETIME
    assert CalendarShareLevel.VIEW_DATETIME < CalendarShareLevel.VIEW_ALL
    assert CalendarShareLevel.VIEW_ALL < CalendarShareLevel.RESPOND
    assert CalendarShareLevel.RESPOND < CalendarShareLevel.MODIFY


def test_share_level_comparison():
    assert CalendarShareLevel.RESPOND >= CalendarShareLevel.VIEW_ALL
    assert not CalendarShareLevel.VIEW_DATETIME >= CalendarShareLevel.MODIFY


# ========== CalendarPermissions helpers ==========

def test_level_for_visibility_public():
    perms = _perms(public=CalendarShareLevel.VIEW_ALL)
    assert perms.level_for_visibility(EventVisibility.PUBLIC) == CalendarShareLevel.VIEW_ALL


def test_level_for_visibility_confidential():
    perms = _perms(confidential=CalendarShareLevel.RESPOND)
    assert perms.level_for_visibility(EventVisibility.CONFIDENTIAL) == CalendarShareLevel.RESPOND


def test_level_for_visibility_private():
    perms = _perms(private=CalendarShareLevel.MODIFY)
    assert perms.level_for_visibility(EventVisibility.PRIVATE) == CalendarShareLevel.MODIFY


def test_level_for_visibility_undefined_defaults_to_public():
    perms = _perms(public=CalendarShareLevel.VIEW_DATETIME)
    assert perms.level_for_visibility(EventVisibility.UNDEFINED) == CalendarShareLevel.VIEW_DATETIME
