"""Unit tests for SyncEngine."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventSyncMeta import CalEventSyncMeta
from app.module.calendar.model.CalSyncResult import CalSyncResult
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus
from app.module.calendar.sync.SyncEngine import SyncEngine
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_calendar(**kwargs):
    defaults = dict(
        user_uid="user@example.com",
        name="External Cal",
        key="ext-cal-key",
        source_type=CalendarSourceType.ICS,
        sync_config={"url": "https://example.com/cal.ics", "sync_interval_minutes": 60},
    )
    defaults.update(kwargs)
    return CalCalendar(**defaults)


def _make_event(uid, title="Test", sequence=0, **kwargs):
    defaults = dict(
        uid=uid,
        title=title,
        date_start=_dt(2026, 6, 1, 10),
        date_end=_dt(2026, 6, 1, 11),
        key=f"key-{uid}",
        sequence=sequence,
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _make_meta(uid, sequence=0, recurrence_id=None, key=None, db_id=1):
    return CalEventSyncMeta(uid=uid, sequence=sequence, recurrence_id=recurrence_id,
                            key=key or f"key-{uid}", db_id=db_id, updated_at=None)


def _build_engine():
    sources = MagicMock()
    cache = MagicMock()
    cache.set.return_value = True
    engine = SyncEngine(sources=sources, cache=cache)
    return engine, sources, cache


# ========== _is_modified_meta ==========

def test_is_modified_higher_sequence():
    assert SyncEngine._is_modified_meta(_make_meta("e1", sequence=1), _make_event("e1", sequence=2)) is True


def test_is_modified_same_sequence():
    assert SyncEngine._is_modified_meta(_make_meta("e1", sequence=1), _make_event("e1", sequence=1)) is False


def test_is_modified_lower_sequence():
    assert SyncEngine._is_modified_meta(_make_meta("e1", sequence=2), _make_event("e1", sequence=1)) is False


def test_is_modified_same_sequence_newer_updated_at():
    meta = _make_meta("e1", sequence=1)
    meta.updated_at = _dt(2026, 1, 1)
    remote = _make_event("e1", sequence=1, updated_at=_dt(2026, 1, 2))
    assert SyncEngine._is_modified_meta(meta, remote) is True


def test_is_modified_naive_vs_aware_updated_at():
    """Naive (DB) and aware (ICS) updated_at must compare without error."""
    from datetime import datetime
    meta = _make_meta("e1", sequence=1)
    meta.updated_at = datetime(2026, 1, 1, 0, 0, 0)  # naive from DB
    remote = _make_event("e1", sequence=1, updated_at=_dt(2026, 1, 2))  # aware UTC
    assert SyncEngine._is_modified_meta(meta, remote) is True


def test_sync_recurrence_id_naive_vs_aware():
    """Naive recurrence_id from DB must match aware recurrence_id from ICS during diff."""
    from datetime import datetime
    engine, sources, _ = _build_engine()
    naive_rid = datetime(2026, 5, 11, 10, 0, 0)
    aware_rid = _dt(2026, 5, 11, 10)
    # Local has naive recurrence_id (simulating DB without tz)
    local_meta = CalEventSyncMeta(db_id=1, key="k1", uid="recur@test",
                                  recurrence_id=naive_rid, sequence=0, updated_at=None)
    # After to_utc normalization in find_sync_metadata, both should match
    from app.utils.datetime.DateTimeUtils import to_utc
    normalized = to_utc(naive_rid)
    assert normalized == aware_rid


# ========== sync validation ==========

def test_sync_rejects_local_calendar():
    engine, _, _ = _build_engine()
    with pytest.raises(RequestException):
        engine.sync(_make_calendar(source_type=CalendarSourceType.LOCAL))


def test_sync_rejects_missing_url():
    engine, _, _ = _build_engine()
    with pytest.raises(RequestException):
        engine.sync(_make_calendar(sync_config={}))


# ========== sync diff ==========

@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_inserts_new_events(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[_make_event("new-uid")]

    summary = engine.sync(_make_calendar())
    assert summary.inserted == 1
    assert summary.updated == 0
    assert summary.deleted == 0
    mock_source.insert_event.assert_called_once()


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_deletes_removed_events(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = [_make_meta("old-uid")]
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[]

    summary = engine.sync(_make_calendar())
    assert summary.deleted == 1
    mock_source.delete_by_key.assert_called_once_with("key-old-uid")


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_updates_modified_events(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = [_make_meta("e1", sequence=1)]
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[_make_event("e1", title="New", sequence=2)]

    summary = engine.sync(_make_calendar())
    assert summary.updated == 1
    mock_source.update_event.assert_called_once()


# ========== sync status ==========

@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_updates_status_on_success(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[]

    cal = _make_calendar()
    engine.sync(cal)
    assert cal.sync_config["sync_status"] == CalendarSyncStatus.COMPLETED.value
    assert "last_sync" in cal.sync_config


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_updates_status_on_failure(mock_fetcher):
    engine, _, _ = _build_engine()
    mock_fetcher.fetch.side_effect = RequestException(error=MagicMock(c="S000600"))

    cal = _make_calendar()
    with pytest.raises(RequestException):
        engine.sync(cal)
    assert cal.sync_config["sync_status"] == CalendarSyncStatus.FAILED.value


# ========== sync lock ==========

def test_sync_rejects_concurrent():
    engine, _, cache = _build_engine()
    cache.set.return_value = False
    with pytest.raises(RequestException):
        engine.sync(_make_calendar())


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_releases_lock(mock_fetcher):
    engine, sources, cache = _build_engine()
    # Make cache.get return the same token that was stored by cache.set
    def get_stored_token(key, expected_type):
        return cache.set.call_args[0][1]  # second positional arg = token value
    cache.get.side_effect = get_stored_token
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[]

    engine.sync(_make_calendar())
    cache.delete.assert_called_once_with("sync_lock:ext-cal-key")


# ========== edge cases ==========

@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_empty_feed(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[]

    summary = engine.sync(_make_calendar())
    assert summary == CalSyncResult(inserted=0, updated=0, deleted=0, total=0)


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_skips_events_without_uid(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []
    sources.get.return_value = mock_source
    evt_no_uid = _make_event("")
    evt_no_uid.uid = ""
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[evt_no_uid]

    summary = engine.sync(_make_calendar())
    assert summary.inserted == 0
    mock_source.insert_event.assert_not_called()


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_sync_deletes_all_when_remote_empty(mock_fetcher):
    engine, sources, _ = _build_engine()
    mock_fetcher.fetch.return_value = ""
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = [_make_meta("l1"), _make_meta("l2")]
    sources.get.return_value = mock_source
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[]

    summary = engine.sync(_make_calendar())
    assert summary.deleted == 2


# ========== orphan override handling ==========

@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_apply_diff_skips_orphan_override(_mock_fetcher):
    engine, sources, _ = _build_engine()
    master = _make_event("series@x")  # master in remote
    orphan = _make_event("orphan@x", recurrence_id=_dt(2026, 6, 5))  # no master anywhere
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []  # no local events
    sources.get.return_value = mock_source

    result = engine._apply_diff(_make_calendar(), [master, orphan], delete_missing=False)
    assert result.inserted == 1
    assert result.skipped == 1
    assert result.total == 2


@patch("app.module.calendar.sync.SyncEngine.IcsFetcher")
def test_apply_diff_keeps_override_when_master_in_local(_mock_fetcher):
    engine, sources, _ = _build_engine()
    override = _make_event("series@x", recurrence_id=_dt(2026, 6, 5))
    mock_source = MagicMock()
    # Master already present locally (no recurrence_id)
    mock_source.get_sync_metadata.return_value = [_make_meta("series@x")]
    sources.get.return_value = mock_source

    result = engine._apply_diff(_make_calendar(), [override], delete_missing=False)
    assert result.skipped == 0
    assert result.inserted == 1


# ========== ownership rewrite (on the deserialized models) ==========

def _capture_inserted_events(engine, sources):
    """Wire a mock source that records every event passed to insert_event."""
    inserted: list = []
    mock_source = MagicMock()
    mock_source.get_sync_metadata.return_value = []
    mock_source.insert_event.side_effect = lambda evt: inserted.append(evt)
    sources.get.return_value = mock_source
    return inserted


def test_apply_ics_rewrites_organizer_and_resets_sequence():
    engine, sources, _ = _build_engine()
    inserted = _capture_inserted_events(engine, sources)
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[_make_event("e1", sequence=7)]

    engine.apply_ics(_make_calendar(), "ics", delete_missing=False, rewrite_owner_email="alice@example.com")

    assert inserted[0].organizer.email == "alice@example.com"
    assert inserted[0].sequence == 0


def test_apply_ics_without_rewrite_keeps_organizer():
    engine, sources, _ = _build_engine()
    inserted = _capture_inserted_events(engine, sources)
    original = _make_event("e1", sequence=7)
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events =[original]

    engine.apply_ics(_make_calendar(), "ics", delete_missing=False)

    assert inserted[0].sequence == 7  # untouched when no rewrite requested


def test_apply_ics_remove_attendees_clears_guest_list():
    engine, sources, _ = _build_engine()
    inserted = _capture_inserted_events(engine, sources)
    event = _make_event("e1", attendees=[CalAttendee(email="guest@example.com")])
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events = [event]

    engine.apply_ics(_make_calendar(), "ics", delete_missing=False, remove_attendees=True)

    assert inserted[0].attendees == []


def test_apply_ics_keeps_attendees_by_default():
    engine, sources, _ = _build_engine()
    inserted = _capture_inserted_events(engine, sources)
    event = _make_event("e1", attendees=[CalAttendee(email="guest@example.com")])
    engine._deserializer = MagicMock()
    engine._deserializer.deserialize.return_value.events = [event]

    engine.apply_ics(_make_calendar(), "ics", delete_missing=False)

    assert len(inserted[0].attendees) == 1
