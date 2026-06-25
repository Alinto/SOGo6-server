from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from app.module.calendar.CalendarConst import REJECT_ATTENDEE_CONTENT_CHANGE
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.rrule.RruleEngine import RruleEngine
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.module.calendar.source.CalendarSource import CalendarSource


class EventAction(Enum):
    """Indicates what happened to an individual event row."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


@dataclasses.dataclass
class ScopeResult:
    """Result of a recurrence scope operation.

    result is the primary CalEvent the caller should return to the client.
    touched is the exhaustive list of (CalEvent, EventAction) pairs that were
    applied on the organizer's calendar, ready for blind replication to attendees.
    """
    result: CalEvent
    touched: list[tuple[CalEvent, EventAction]]
    # When the master's date_start moved, attendee calendars must realign their
    # detached occurrences. Storing the old/new start avoids including realigned
    # events in touched (their recurrence_id has shifted and wouldn't match the
    # attendee's copy for an UPDATE lookup).
    realign_from: datetime | None = None
    realign_to: datetime | None = None


class RecurrenceScopeProcessor:
    """Handles recurrence scope operations for recurring events.

    When a user modifies a recurring event, three scopes are possible:

    1. **This event only** (split_occurrence) - A single occurrence is overridden by
       inserting a detached occurrence row (RFC 5545 RECURRENCE-ID without RANGE).
       The master event is untouched; the RRULE expander prefers the detached row.

    2. **This and following events** (split_series) - The original series is truncated
       just before the target date, and a new independent master is optionally created
       from that date onward. Data is duplicated: the new master carries its own RRULE
       and uid_parent_split links back to the original series for traceability.

    3. **All events** - Standard update applied directly to the event.

    All methods are static. event_update is always a fully merged CalEvent produced by
    deserialize_with_update (origin + body changes). The processor uses it directly
    for construction - no field-level detection or sentinel logic needed.
    Propagation to attendees is handled by the caller (ModuleCalendar).
    """

    @staticmethod
    def process(source: CalendarSource, original: CalEvent, event_update: CalEvent) -> ScopeResult:
        """Dispatch a recurrence-scoped update to the appropriate handler.

        Returns a ScopeResult carrying the resulting CalEvent and the full list of
        touched (CalEvent, EventAction) pairs persisted on the organizer's calendar.
        """
        # Branch 1: "This and following events" - split the series at recurrence_id
        if not original.is_detached and event_update.recurrence_id is not None and event_update.recurrence_range == "THISANDFUTURE":
            if original.recurrence_rule is None:
                raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_RECURRING)
            return RecurrenceScopeProcessor._process_split_series(source, original, event_update)

        # Branch 2: "This event only" - create a detached occurrence override
        if not original.is_detached and event_update.recurrence_id is not None:
            if original.recurrence_rule is None:
                raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_RECURRING)
            occurrence: CalEvent = RecurrenceScopeProcessor.split_occurrence(source, original, event_update)
            return ScopeResult(result=occurrence, touched=[(occurrence, EventAction.INSERT)])

        # Branch 3: "All events" (or standalone/detached event) - standard update
        event_update.normalize_all_day()
        event_update.sequence = (original.sequence or 0) + 1
        # A reschedule by the organizer invalidates prior replies (RFC 5546 2.1.4): reset attendee
        # PARTSTAT so the re-sent REQUEST prompts a fresh confirmation. Same-entity comparison here,
        # so no false positive from the master/occurrence date offset.
        if original.has_scheduling_changes(event_update):
            event_update.reset_attendee_responses()
        source.update_event(event_update)
        touched: list[tuple[CalEvent, EventAction]] = [(event_update, EventAction.UPDATE)]

        # If the master's start time moved, realign all detached occurrences
        realign_from: datetime | None = None
        realign_to: datetime | None = None
        if (
            not original.is_detached
            and original.date_start is not None
            and event_update.date_start is not None
            and original.date_start != event_update.date_start
        ):
            source.realign_detached_occurrences(
                uid=event_update.require_uid, old_start=original.date_start, new_start=event_update.date_start,
            )
            realign_from = original.date_start
            realign_to = event_update.date_start
        return ScopeResult(
            result=event_update, touched=touched, realign_from=realign_from, realign_to=realign_to,
        )

    @staticmethod
    def process_delete(source: CalendarSource, event: CalEvent) -> ScopeResult:
        """Dispatch a recurrence-scoped deletion and return the touched row.

        A detached occurrence is removed alone (its slot is added to the master EXDATE by the
        source); any other event removes the whole series. Returns a ScopeResult with the deleted
        event ready for blind replication to attendees - the caller decides whether to propagate.
        """
        if event.recurrence_id is not None:
            source.delete_occurrence(event)
        else:
            source.delete_event(event.require_uid)
        return ScopeResult(result=event, touched=[(event, EventAction.DELETE)])

    @staticmethod
    def process_attendee_edit(source: CalendarSource, original: CalEvent, event_update: CalEvent) -> CalEvent:
        """Apply a non-organizer attendee's personal-field edit to the row being edited.

        The attendee never creates structure: the personal fields land on the row event_key points to
        (the master = whole series, or an existing detached occurrence). Any organizer-content change
        is rejected. When the client scopes to an occurrence of a non-detached series, the row's date
        is projected onto that slot so the occurrence date is not mistaken for a content change.
        """
        baseline: CalEvent = original
        if event_update.recurrence_id is not None and original.recurrence_id is None:
            duration: timedelta = original.require_date_end - original.require_date_start
            baseline = dataclasses.replace(
                original, date_start=event_update.recurrence_id, date_end=event_update.recurrence_id + duration,
            )
        if REJECT_ATTENDEE_CONTENT_CHANGE and baseline.has_organizer_content_changes(event_update):
            raise RequestException(error=err.ERROR_CALENDAR_NOT_ORGANIZER)
        original.apply_personal_fields(event_update)
        return source.update_event_or_fail(original, "applying attendee personal update")

    @staticmethod
    def split_occurrence(source: CalendarSource, original: CalEvent, event_update: CalEvent) -> CalEvent:
        """Create a detached occurrence that overrides a single slot of a recurring series.

        RFC 5545 §3.8.4.4: a VEVENT with RECURRENCE-ID (no RANGE) replaces exactly the
        named occurrence. The master is never modified; the RRULE expander will prefer
        this detached row over the generated slot.
        """
        recurrence_id: datetime = event_update.require_recurrence_id
        duration: timedelta = original.require_date_end - original.require_date_start

        # Use dates from event_update if they differ from the original (body provided new dates,
        # e.g. drag & drop). Otherwise default to the recurrence_id slot.
        has_new_dates: bool = event_update.date_start != original.date_start
        start: datetime = event_update.require_date_start if has_new_dates else recurrence_id
        end: datetime = event_update.require_date_end if has_new_dates else recurrence_id + duration

        occurrence: CalEvent = dataclasses.replace(
            event_update,
            key=None,
            db_id=None,
            uid=original.uid,
            recurrence_id=recurrence_id,
            recurrence_rule=None,
            recurrence_range=None,
            date_start=start,
            date_end=end,
            sequence=0,
        )
        occurrence.normalize_all_day()
        # Moving this occurrence off its slot reschedules it: attendees must re-confirm. Detection is
        # against the slot (recurrence_id), not the master, to avoid flagging an unmoved occurrence
        # whose date naturally differs from the series start.
        if start != recurrence_id:
            occurrence.reset_attendee_responses()
        return source.insert_event(occurrence)

    @staticmethod
    def _process_split_series(source: CalendarSource, original: CalEvent, event_update: CalEvent) -> ScopeResult:
        """Build a ScopeResult for a THISANDFUTURE split, collecting all touched events."""
        from_dt: datetime = event_update.require_recurrence_id
        until: datetime = from_dt - timedelta(seconds=1)
        touched: list[tuple[CalEvent, EventAction]] = list(source.split_event(original.require_uid, until, from_dt))
        result: CalEvent = RecurrenceScopeProcessor.split_series(source, original, event_update)
        if result.uid != original.uid:
            touched.append((result, EventAction.INSERT))
        return ScopeResult(result=result, touched=touched)

    @staticmethod
    def split_series(source: CalendarSource, original: CalEvent, event_update: CalEvent) -> CalEvent:
        """Split a recurring series at event_update.recurrence_id.

        The original series is truncated just before the target date (UNTIL = target - 1s).
        COUNT is always converted to UNTIL on both the original and new series because
        the remaining occurrence count changes after the split (RFC 5545 §3.3.10).

        If event_update carries content changes (fields differ from original), a new
        independent master is created from the split point with uid_parent_split.
        If no content changes, the series is simply truncated ("delete this and following").
        """
        from_dt: datetime = event_update.require_recurrence_id

        if not original.has_content_changes(event_update):
            return source.get_master_event_by_uid(original.require_uid) or original

        duration: timedelta = original.require_date_end - original.require_date_start

        # Anchor the new series at the occurrence date the client provided. When the client omits it,
        # the merged date_start still equals the master's, so fall back to the split slot - the new
        # series must not jump to the master's start.
        client_date_provided: bool = event_update.date_start != original.date_start
        new_start: datetime = event_update.require_date_start if client_date_provided else from_dt
        new_end: datetime = event_update.require_date_end if client_date_provided else from_dt + duration

        new_master: CalEvent = dataclasses.replace(
            event_update,
            key=None,
            db_id=None,
            uid=generate_uuid(),
            date_start=new_start,
            date_end=new_end,
            recurrence_id=None,
            recurrence_range=None,
            sequence=0,
            uid_parent_split=original.uid,
        )
        new_master.normalize_all_day()

        # A reschedule (moved off the split slot, or recurrence/timezone/all-day changed) invalidates
        # prior replies on the affected occurrences (RFC 5546 2.1.4).
        rescheduled: bool = (
            new_start != from_dt
            or event_update.all_day != original.all_day
            or event_update.timezone != original.timezone
            or event_update.recurrence_rule != original.recurrence_rule
            or event_update.recurrence_exceptions != original.recurrence_exceptions
        )
        if rescheduled:
            new_master.reset_attendee_responses()

        # Convert COUNT to UNTIL on the new series
        if new_master.recurrence_rule is not None and new_master.recurrence_rule.count is not None:
            max_date: datetime | None = RruleEngine().get_max_date(new_master)
            if max_date is not None:
                new_master.recurrence_rule.until = max_date
            new_master.recurrence_rule.count = None

        created: CalEvent = source.insert_event(new_master)
        logger_calendar.info("Split series uid=%s at %s -> new master uid=%s", original.uid, from_dt, created.uid)
        return created
