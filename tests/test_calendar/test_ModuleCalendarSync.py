"""Unit tests for ModuleCalendar external-calendar sync (manual enqueue, auto sweep, due logic)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc
_MOD = "app.module.calendar.ModuleCalendar"


def _user(uid="alice@example.com"):
    user = MagicMock()
    user.uid = uid
    return user


def _ics_cal(key="cal-1", sync_config=None, source_type=CalendarSourceType.ICS):
    return CalCalendar(
        key=key, user_uid="alice@example.com", name="Ext", ctag=0, timezone="UTC",
        source_type=source_type, sync_config=sync_config if sync_config is not None else {"url": "http://x/c.ics"},
    )


def _source(cal):
    source = MagicMock()
    source.calendar = cal
    return source


def _build_module():
    module = object.__new__(ModuleCalendar)
    module._db = MagicMock()
    module._cache = MagicMock()
    module._acl = MagicMock()
    module._sources = MagicMock()
    module._agent = MagicMock()
    module._agent.enqueue.return_value = "job-1"
    return module


# ========== enqueue_sync (manual) ==========

def test_enqueue_sync_enqueues_for_ics_calendar():
    module = _build_module()
    module._sources.get_by_key.return_value = _source(_ics_cal("cal-9"))
    job_id = module.enqueue_sync(_user(), "cal-9")
    assert job_id == "job-1"
    req = module._agent.enqueue.call_args.args[0]
    assert req.calendar_key == "cal-9" and req.name == "calendar.sync.external.manual"


def test_enqueue_sync_unknown_calendar_raises():
    module = _build_module()
    module._sources.get_by_key.return_value = None
    with pytest.raises(RequestException) as ex:
        module.enqueue_sync(_user(), "missing")
    assert ex.value.error == err.ERROR_CALENDAR_NOT_FOUND
    module._agent.enqueue.assert_not_called()


def test_enqueue_sync_non_ics_raises():
    module = _build_module()
    module._sources.get_by_key.return_value = _source(_ics_cal("cal-1", source_type=CalendarSourceType.LOCAL))
    with pytest.raises(RequestException) as ex:
        module.enqueue_sync(_user(), "cal-1")
    assert ex.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED
    module._agent.enqueue.assert_not_called()


def test_enqueue_sync_requires_agent():
    module = _build_module()
    module._agent = None
    with pytest.raises(RuntimeError):
        module.enqueue_sync(_user(), "cal-1")


# ========== _is_sync_due ==========

def test_is_sync_due_never_synced():
    assert ModuleCalendar._is_sync_due(_ics_cal(sync_config={"url": "x"}), datetime.now(_UTC)) is True


def test_is_sync_due_running_is_skipped():
    cal = _ics_cal(sync_config={"sync_status": CalendarSyncStatus.RUNNING.value, "last_sync": None})
    assert ModuleCalendar._is_sync_due(cal, datetime.now(_UTC)) is False


def test_is_sync_due_interval_elapsed():
    now = datetime(2026, 6, 20, 12, 0, tzinfo=_UTC)
    cal = _ics_cal(sync_config={"last_sync": (now - timedelta(minutes=61)).isoformat(), "sync_interval_minutes": 60})
    assert ModuleCalendar._is_sync_due(cal, now) is True


def test_is_sync_due_interval_not_elapsed():
    now = datetime(2026, 6, 20, 12, 0, tzinfo=_UTC)
    cal = _ics_cal(sync_config={"last_sync": (now - timedelta(minutes=10)).isoformat(), "sync_interval_minutes": 60})
    assert ModuleCalendar._is_sync_due(cal, now) is False


# ========== sync_all_due_external (auto sweep) ==========

def test_sync_all_due_external_syncs_due_skips_others():
    module = _build_module()
    due = _ics_cal("due", {"url": "x"})  # never synced -> due
    recent = _ics_cal("recent", {"last_sync": datetime.now(_UTC).isoformat(), "sync_interval_minutes": 60})
    engine = MagicMock()
    with patch(f"{_MOD}.RepositoryCalendar") as repo_cls, patch(f"{_MOD}.SyncEngine", return_value=engine):
        repo_cls.return_value.find_all_external.return_value = [due, recent]
        counts = module.sync_all_due_external()
    assert counts == {"total": 2, "synced": 1, "failed": 0, "skipped": 1}
    engine.sync.assert_called_once_with(due)


def test_sync_all_due_external_isolates_failures():
    module = _build_module()
    engine = MagicMock()
    engine.sync.side_effect = [RequestException(error=err.ERROR_CALENDAR_ICS_FETCH_FAILED), None]
    with patch(f"{_MOD}.RepositoryCalendar") as repo_cls, patch(f"{_MOD}.SyncEngine", return_value=engine):
        repo_cls.return_value.find_all_external.return_value = [_ics_cal("a", {"url": "x"}), _ics_cal("b", {"url": "y"})]
        counts = module.sync_all_due_external()
    assert counts == {"total": 2, "synced": 1, "failed": 1, "skipped": 0}
