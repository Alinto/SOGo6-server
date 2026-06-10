from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.module.calendar.CalendarConst import (
    IMPORT_REMOVES_ATTENDEES, IMPORT_REWRITES_OWNERSHIP, MAX_EVENT_FETCH_DAYS, MAX_FREEBUSY_DAYS,
    MAX_IMPORT_ICS_BYTES, MAX_TASK_FETCH_DAYS, PUBLIC_SUBSCRIPTION_REFRESH, SHARE_TOKEN_LENGTH,
)
from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal
from app.module.calendar.serializer.CalendarEventsSerializerIcal import CalendarEventsSerializerIcal
from app.module.calendar.serializer.CalendarSerializerIcal import CalendarSerializerIcal
from app.module.calendar.freebusy.FreeBusyEngine import FreeBusyEngine, FreeBusyPrefs
from app.module.calendar.imip.ImipBuilder import ImipBuilder
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.acl.CalendarAclEngine import CalendarAclEngine
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.model.CalendarUser import CalendarUser
from app.module.calendar.model.enums.CalendarPermissionAction import CalendarPermissionAction
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.CalSyncResult import CalSyncResult
from app.module.calendar.model.CalSyncStatus import CalSyncStatus
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus
from app.module.calendar.reminder.ReminderEngine import ReminderEngine
from app.module.calendar.repository.RepositoryEvent import RepositoryEvent
from app.module.calendar.repository.RepositoryReminder import RepositoryReminder
from app.module.calendar.sync.SyncEngine import SyncEngine
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction, RecurrenceScopeProcessor, ScopeResult
from app.module.calendar.source.CalendarSources import CalendarSources
from app.utils import errors as err
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_calendar
from app.utils.maths.sogo_hash import generate_uuid, get_unique_token
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis
    from app.manager.db.ClientSQL import ClientSQL

    from app.module.calendar.imip.ImipMessage import ImipMessage
    from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
    from app.module.calendar.source.CalendarSource import CalendarSource


class ModuleCalendar:  # pylint: disable=too-many-public-methods
    """Module for calendar and event operations."""

    def __init__(self, process_settings: ProcessSetting, cache: ClientRedis | None = None) -> None:
        sogo_db_type: str = f"Client{process_settings.SOGO_P_DB_TYPE}"
        self._db: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=process_settings.get_db_settings(),
        )
        self._db.connect()
        self._cache: ClientRedis | None = cache
        self._sources: CalendarSources = CalendarSources(self._db)
        self._imip: ImipProcessor = ImipProcessor(self._sources)
        self._acl: CalendarAclEngine = CalendarAclEngine()

    def __del__(self) -> None:
        if hasattr(self, "_db"):
            self._db.close()

    def create_personal_calendar(self, user_uid: str, name: str = "Personal Calendar", tz: str = "UTC") -> CalCalendar:
        """Create and persist the default personal calendar for a user.

        If the user already has a default calendar, returns it without creating a new one.
        The caller (auth onboarding) passes the user's preferred timezone (``tz``) so
        floating-time events imported later are anchored to the user's locale rather than UTC.
        """
        for source in self._sources.get_all(user_uid):
            if source.calendar.is_default:
                return source.calendar
        cal: CalCalendar = CalCalendar(
            user_uid=user_uid, name=name, timezone=tz,
            is_default=True, source_type=CalendarSourceType.LOCAL,
        )
        cal.key = generate_uuid()
        cal.ctag = 0
        source = self._sources.get(cal)
        return source.save_calendar(cal)

    #
    # Calendars
    #
    def get_all_calendars(self, user: User, shared_keys: list[str] | None = None) -> list[CalCalendar]:
        """Return all calendars accessible by the user.

        Includes owned calendars and optionally shared calendars identified by key.
        Each calendar is populated with the user's permissions.

        :param user: The authenticated user.
        :param shared_keys: Additional calendar keys to include (from the ACL module).
        """
        calendar_user: CalendarUser = CalendarUser(user=user, owner=user)
        # Owned calendars
        sources: list[CalendarSource] = self._sources.get_all(user.uid)
        # Delegated calendars (shared by other users, keys provided by the ACL module)
        if shared_keys:
            for key in shared_keys:
                source: CalendarSource | None = self._sources.get_by_key(user.uid, key)
                if source is not None:
                    sources.append(source)
        calendars: list[CalCalendar] = []
        for source in sources:
            cal: CalCalendar = source.calendar
            cal.permissions = self._acl.get_permissions(cal, calendar_user)
            calendars.append(cal)
        return calendars

    def get_calendar(self, user: User, key: str) -> CalendarSource:
        """Return the source for a calendar, or raise NOT_FOUND. Populates permissions."""
        calendar_user: CalendarUser = CalendarUser(user=user, owner=user)
        source: CalendarSource | None = self._sources.get_by_key(user.uid, key)
        if source is None:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
        source.calendar.permissions = self._acl.get_permissions(source.calendar, calendar_user)
        return source

    def create_calendar(self, user: User, cal: CalCalendar) -> CalCalendar:
        """Persist a new calendar. Generates key and ctag."""
        cal.user_uid = user.uid
        cal.key = generate_uuid()
        cal.ctag = 0
        source: CalendarSource = self._sources.get(cal)
        return source.save_calendar(cal)

    def update_calendar(self, user: User, key: str, updates: dict) -> CalCalendar:
        """Apply updates to an existing calendar and persist it."""
        source: CalendarSource = self.get_calendar(user, key)
        cal: CalCalendar = source.calendar
        cal.apply_update(updates)
        source.update_calendar(cal)
        return cal

    def delete_calendar(self, user: User, key: str) -> None:
        """Delete a calendar and all its events."""
        source: CalendarSource = self.get_calendar(user, key)
        source.delete_calendar()

    #
    # Events — internal helpers
    #
    @staticmethod
    def _normalize_all_day(event: CalEvent) -> None:
        """Ensure all-day events have a valid exclusive DTEND (RFC 5545 §3.6.1).

        For all-day events, DTEND must be strictly greater than DTSTART.
        If date_end <= date_start, advance date_end to date_start + 1 day.
        """
        if event.all_day and event.date_end is not None and event.date_start is not None and event.date_end <= event.date_start:
            event.date_end = event.date_start + timedelta(days=1)

    def _find_source_for_event(self, calendar_user: CalendarUser, event_key: str) -> tuple[CalendarSource, CalEvent]:
        """Find the source and event by event_key (opaque UUID stored in the key column of sogo_events, not the uid)."""
        for source in self._sources.get_all(calendar_user.owner.uid):
            event: CalEvent | None = source.get_event(event_key)
            if event is not None:
                return source, event
        raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)

    def _find_source_for_event_by_uid(self, calendar_user: CalendarUser, uid: str) -> tuple[CalendarSource, CalEvent]:
        """Find the source and master event by RFC 5545 UID (semantic identifier) across user's calendars."""
        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(calendar_user.owner.uid, uid)
        if result is None:
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)

        return result

    def _find_default_source(self, calendar_user: CalendarUser) -> CalendarSource:
        """Return the user's default writable calendar source, or raise NOT_FOUND."""
        source: CalendarSource | None = self._sources.get_default(calendar_user.owner.uid)
        if source is None:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)

        return source

    #
    # Events — CRUD
    #
    def create_event(self, calendar_user: CalendarUser, calendar_key: str, event: CalEvent, organizer: CalOrganizer) -> CalEvent:
        """Persist a new event in the calendar and propagate it to local attendees."""
        event.apply_defaults()
        source: CalendarSource = self.get_calendar(calendar_user.owner, calendar_key)
        self._acl.check_permission(source.calendar.permissions, CalendarPermissionAction.CREATE)
        event.calendar_key = source.calendar.key
        if not event.uid:
            event.uid = generate_uuid()
        if not event.organizer:
            event.organizer = organizer
        self._normalize_all_day(event)
        event.validate()
        try:
            created: CalEvent = source.insert_event(event)
            # Propagate changes to attendees
            self._sources.propagate(scope_result=ScopeResult(
                result=created, touched=[(created, EventAction.INSERT)],
            ))
            imip_msg: ImipMessage | None = ImipBuilder.build_request(created)
            if imip_msg:
                logger_calendar.info("iMIP REQUEST built for event %s to %s", created.uid, imip_msg.to_emails)
                # TODO: dispatch imip_msg via agent transport (Celery + SMTP) once the agent is in place
            return created
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error creating event in calendar %s", calendar_key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED) from exc

    def get_event(self, calendar_user: CalendarUser, event_key: str) -> CalEvent:
        """Return a single event by key across the user's calendars, or raise NOT_FOUND."""
        _, event = self._find_source_for_event(calendar_user, event_key)
        return event

    def update_event(self, calendar_user: CalendarUser, event_key: str, event_update: CalEvent, organizer: CalOrganizer) -> CalEvent:
        """Update an event, handling recurrence scope and attendee propagation."""
        source, event = self._find_source_for_event(calendar_user, event_key)
        perms: CalendarPermissions = self._acl.get_permissions(source.calendar, calendar_user)
        self._acl.check_permission(perms, CalendarPermissionAction.MODIFY)
        # Only the organizer can modify event content (RFC 5545 §3.8.4.3)
        if event.organizer and event.organizer.email != calendar_user.owner.mail:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_ORGANIZER)
        event_update.validate()

        try:
            scope_result: ScopeResult = RecurrenceScopeProcessor.process(source=source, original=event, event_update=event_update)

            if not scope_result.result.organizer:
                scope_result.result.organizer = organizer

            # Propagate changes to attendeees
            self._sources.propagate(scope_result=scope_result, original=event)

            imip_msg: ImipMessage | None = ImipBuilder.build_request(scope_result.result)
            if imip_msg:
                logger_calendar.info("iMIP REQUEST built for updated event %s to %s", scope_result.result.uid, imip_msg.to_emails)
            return scope_result.result
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error updating event %s", event_key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

    def delete_event(self, calendar_user: CalendarUser, event_key: str) -> None:
        """Soft-delete an event by key and propagate the deletion to attendees.

        If the event is a detached occurrence, only that row is deleted and its
        recurrence_id is added to the master's EXDATE.
        If the user is the organizer, the deletion is propagated to all attendees.
        If the user is an attendee, only their own copy is deleted.
        """
        source, event = self._find_source_for_event(calendar_user, event_key)
        self._acl.check_permission(
            self._acl.get_permissions(source.calendar, calendar_user), CalendarPermissionAction.DELETE,
        )
        try:
            if event.recurrence_id is not None:
                source.delete_detached_occurrence(event)
            else:
                source.delete_event(event.require_uid)
            # Propagate deletion to attendees if the user is the organizer
            is_organizer: bool = bool(event.organizer and event.organizer.email == calendar_user.owner.mail)
            if is_organizer:
                self._sources.propagate(scope_result=ScopeResult(
                    result=event, touched=[(event, EventAction.DELETE)],
                ))
            imip_msg: ImipMessage | None = ImipBuilder.build_cancel(event)
            if imip_msg:
                logger_calendar.info("iMIP CANCEL built for event %s to %s", event.uid, imip_msg.to_emails)
                # TODO: dispatch imip_msg via agent transport (Celery + SMTP) once the agent is in place
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error deleting event %s", event_key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def get_events(
        self,
        calendar_user: CalendarUser,
        start: datetime | None,
        end: datetime | None,
        search: str | None,
        key: str | None = None,
    ) -> list[CalEvent]:
        """Return events within [start, end], optionally restricted to a single calendar.

        When key is None, events from all user calendars are merged.
        The date-range limit is bypassed when a search query is present.
        """
        if search is None and start is not None and end is not None:
            if (end - start) > timedelta(days=MAX_EVENT_FETCH_DAYS):
                raise RequestException(error=err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE)
        try:
            events: list[CalEvent] = self._sources.get_events(calendar_user.owner.uid, start, end, search, key)
            logger_calendar.debug("returned %d events (calendar=%s)", len(events), key or "all")
            return events
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error fetching events (calendar=%s)", key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    #
    # Attendance
    #
    def set_attendance_status(
        self, calendar_user: CalendarUser, event_key: str, status: AttendeeStatus, recurrence_id: datetime | None = None,
    ) -> CalEvent:
        """Update the current user's attendance status (PARTSTAT) for an event.

        When recurrence_id is provided, the status applies to a single occurrence only.
        A detached occurrence is created if it does not already exist.
        Does not increment SEQUENCE — PARTSTAT is not a content change (RFC 5545 §3.8.7.4).
        Propagates the status to all other local copies of the event (organizer + other attendees).

        :param user: The attendee updating their status.
        :param event_key: Opaque key of the attendee's own copy of the event.
        :param status: The new attendance status.
        :param recurrence_id: When set, target a single occurrence instead of the whole event.
        :return: The updated event or occurrence.
        """
        source, event = self._find_source_for_event(calendar_user, event_key)
        self._acl.check_permission(
            self._acl.get_permissions(source.calendar, calendar_user), CalendarPermissionAction.RESPOND,
        )

        # Single occurrence: create or find a detached occurrence for this date
        if recurrence_id is not None:
            event = source.get_or_create_occurrence(event, recurrence_id)

        for attendee in event.attendees:
            if attendee.email == calendar_user.owner.mail:
                attendee.status = status
                break
        try:
            source.update_event(event)
            source.propagate_partstat_to_copies(event, calendar_user.owner.mail, status)
            imip_msg: ImipMessage | None = ImipBuilder.build_reply(event, calendar_user.user)
            if imip_msg:
                logger_calendar.info("iMIP REPLY built for event %s to %s", event.uid, imip_msg.to_emails)
                # TODO: dispatch imip_msg via agent transport (Celery + SMTP) once the agent is in place
            return event
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error updating attendance for event %s", event_key)
            raise RequestException(error=err.ERROR_CALENDAR_ATTENDANCE_UPDATE_FAILED) from exc


    #
    # iMIP — thin wrappers delegating to ImipProcessor
    #
    def process_imip_reply(self, calendar_user: CalendarUser, ical_bytes: bytes, from_email: str) -> CalEvent:
        """Process an incoming iMIP REPLY. Delegates to ImipProcessor."""
        return self._imip.process_reply(calendar_user.user, ical_bytes, from_email)

    def process_imip_request(self, calendar_user: CalendarUser, ical_bytes: bytes, from_email: str) -> CalEvent:
        """Process an incoming iMIP REQUEST. Delegates to ImipProcessor."""
        return self._imip.process_request(calendar_user.user, ical_bytes, from_email)

    def process_imip_cancel(self, calendar_user: CalendarUser, ical_bytes: bytes, from_email: str) -> None:
        """Process an incoming iMIP CANCEL. Delegates to ImipProcessor."""
        self._imip.process_cancel(calendar_user.user, ical_bytes, from_email)

    #
    # Tasks
    #
    def create_task(self, calendar_user: CalendarUser, calendar_key: str, task: CalEvent) -> CalEvent:
        """Persist a new VTODO in the calendar and return it."""
        task.apply_defaults()
        task.component_type = ComponentType.TASK
        source: CalendarSource = self.get_calendar(calendar_user.owner, calendar_key)
        self._acl.check_permission(source.calendar.permissions, CalendarPermissionAction.CREATE)
        task.calendar_key = source.calendar.key
        if not task.uid:
            task.uid = generate_uuid()
        try:
            created: CalEvent = source.insert_event(task)
            return created
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error creating task in calendar %s", calendar_key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED) from exc

    def get_task(self, calendar_user: CalendarUser, task_key: str) -> CalEvent:
        """Return a single VTODO by key, or raise TASK_NOT_FOUND."""
        _, task = self._find_source_for_event(calendar_user, task_key)
        if task.component_type != ComponentType.TASK:
            raise RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
        return task

    def update_task(self, calendar_user: CalendarUser, task_key: str, task_update: CalEvent) -> CalEvent:
        """Persist an already-merged VTODO update."""
        source, task = self._find_source_for_event(calendar_user, task_key)
        if task.component_type != ComponentType.TASK:
            raise RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
        self._acl.check_permission(
            self._acl.get_permissions(source.calendar, calendar_user), CalendarPermissionAction.MODIFY,
        )
        try:
            source.update_event(task_update)
            return task_update
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error updating task %s", task_key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

    def delete_task(self, calendar_user: CalendarUser, task_key: str) -> None:
        """Soft-delete a VTODO by key."""
        source, task = self._find_source_for_event(calendar_user, task_key)
        if task.component_type != ComponentType.TASK:
            raise RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
        self._acl.check_permission(
            self._acl.get_permissions(source.calendar, calendar_user), CalendarPermissionAction.DELETE,
        )
        try:
            source.delete_event(task.require_uid)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error deleting task %s", task_key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def get_tasks(
        self,
        calendar_user: CalendarUser,
        start: datetime | None,
        end: datetime | None,
        search: str | None,
        key: str | None = None,
    ) -> list[CalEvent]:
        """Return VTODO tasks within [start, end], optionally restricted to a single calendar.

        When key is None, tasks from all user calendars are merged.
        The date-range limit is bypassed when a search query is present.
        """
        if search is None and start is not None and end is not None:
            if (end - start) > timedelta(days=MAX_TASK_FETCH_DAYS):
                raise RequestException(error=err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE)
        try:
            tasks: list[CalEvent] = self._sources.get_tasks(calendar_user.owner.uid, start, end, search, key)
            logger_calendar.debug("returned %d tasks (calendar=%s)", len(tasks), key or "all")
            return tasks
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error fetching tasks (calendar=%s)", key)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    #
    # Reminders
    #
    def get_reminders(
        self,
        calendar_user: CalendarUser,
        method: ReminderMethod | None = None,
        lookahead_minutes: int = 0,
    ) -> list[CalEventReminder]:
        """Return currently active reminders for the user.

        A reminder is active from trigger_at (= date_start - minutes_before)
        until event.date_end + lookahead_minutes. For recurring events, occurrences
        are expanded and each is checked independently.

        User filtering is done in SQL via JOIN (reminders → events → calendars).

        :param user: The user whose reminders to fetch.
        :param method: Optional method filter (popup / email).
        :param lookahead_minutes: Extra minutes after event end before the reminder expires (default 0).
        """
        now: datetime = datetime.now(timezone.utc)
        repo_reminder: RepositoryReminder = RepositoryReminder(self._db)

        past_bound: datetime = now - timedelta(days=MAX_EVENT_FETCH_DAYS)
        reminders: list[CalEventReminder] = repo_reminder.find_pending(
            start=past_bound, end=now, user_uid=calendar_user.owner.uid, method=method,
        )

        # Batch-load full CalEvent objects to enrich reminders with title/location/timezone
        # and to provide RRULE expansion for recurring events.
        events_by_key: dict[str, CalEvent] = {}
        for reminder in reminders:
            if reminder.event_key not in events_by_key:
                try:
                    _, found_event = self._find_source_for_event(calendar_user, reminder.event_key)
                    events_by_key[reminder.event_key] = found_event
                except RequestException:
                    continue

        # Enrich reminders with event context from the blob
        for reminder in reminders:
            event: CalEvent | None = events_by_key.get(reminder.event_key)
            if event is not None:
                reminder.title = event.title
                reminder.location = event.location
                reminder.timezone = event.timezone
                reminder.calendar_timezone = getattr(event, "calendar_timezone", None)

        return ReminderEngine().compute_active(
            reminders=reminders,
            events_by_key=events_by_key,
            now=now,
            lookahead_minutes=lookahead_minutes,
        )

    #
    # Import / Export
    #
    def export_calendar(
        self, user: User, key: str,
        date_start: datetime | None = None, date_end: datetime | None = None,
    ) -> str:
        """Serialize all events and tasks of a calendar to a VCALENDAR string.

        Recurring masters are exported with their RRULE intact; expansion happens client-side.
        ``date_start`` and ``date_end`` bound the export window on event ``date_start`` /
        recurrence end; both are optional and default to no bound on their side (1970 → +∞).

        :param user: The calendar owner triggering the export.
        :param key: Opaque calendar key.
        :param date_start: Optional lower bound on event date_start.
        :param date_end: Optional upper bound on event date_start (recurring masters whose
            window reaches this date are included).
        :return: A VCALENDAR string ready to be served as ``text/calendar``.
        """
        # TODO: dispatch as Celery task instead of synchronous call once the agent is in place
        source: CalendarSource = self.get_calendar(user, key)
        self._acl.check_permission(source.calendar.permissions, CalendarPermissionAction.VIEW)
        return self._serialize_calendar_to_ics(source, date_start, date_end)

    @staticmethod
    def _serialize_calendar_to_ics(
        source: CalendarSource, date_start: datetime | None = None, date_end: datetime | None = None,
        refresh_interval: timedelta | None = None,
    ) -> str:
        """Serialize a calendar (header + events and tasks) to a VCALENDAR string.

        expand=False keeps recurring masters with their RRULE intact and includes VTODO,
        so the output mirrors the stored components rather than flat occurrences.
        ``refresh_interval`` advertises a resync period — set for live subscription feeds only.
        """
        events: list[CalEvent] = source.get_events(date_start, date_end, expand=False)
        events.extend(source.get_tasks(date_start, date_end, expand=False))
        source.calendar.events = events
        serializer: CalendarSerializerIcal = CalendarSerializerIcal(
            CalendarEventsSerializerIcal(CalendarEventSerializerIcal()), refresh_interval=refresh_interval,
        )
        return serializer.serialize(source.calendar)

    def import_calendar(self, user: User, key: str, ics_text: str) -> CalSyncResult:
        """Import a VCALENDAR payload into a writable calendar (additive merge).

        The importer takes ownership of every imported event when
        :data:`CalendarConst.IMPORT_REWRITES_OWNERSHIP` is True: the organizer is rewritten
        to the importer and the SEQUENCE reset. Attendees are preserved unless
        :data:`CalendarConst.IMPORT_REMOVES_ATTENDEES` is True, in which case the guest list
        is stripped from every imported event. Events with the same UID as an existing local
        row are updated; events absent from the payload are left untouched (unlike a mirror
        sync).

        Events whose datetimes carry no explicit timezone (RFC 5545 floating time) are
        anchored to the destination calendar's timezone — itself defaulted to the user's
        timezone at creation time.

        :param user: The user importing the file (becomes the new organizer when rewriting).
        :param key: Opaque key of the destination calendar.
        :param ics_text: Raw VCALENDAR payload (UTF-8 decoded).
        :return: Counters of inserted, updated and deleted rows (deleted is always 0).
        :raises RequestException: ERROR_CALENDAR_NOT_SUPPORTED if the target calendar is not
            writable (ICS mirror, denied permission); ERROR_CALENDAR_IMPORT_TOO_LARGE if the
            payload exceeds the size limit.
        """
        # TODO: dispatch as Celery task instead of synchronous call once the agent is in place
        if len(ics_text.encode("utf-8")) > MAX_IMPORT_ICS_BYTES:
            raise RequestException(error=err.ERROR_CALENDAR_IMPORT_TOO_LARGE)
        source: CalendarSource = self.get_calendar(user, key)
        self._acl.check_permission(source.calendar.permissions, CalendarPermissionAction.CREATE)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        if self._cache is None:
            raise BugException("ModuleCalendar requires a cache for calendar sync")
        engine: SyncEngine = SyncEngine(sources=self._sources, cache=self._cache)
        return engine.apply_ics(
            source.calendar, ics_text,
            delete_missing=False,
            default_timezone=source.calendar.timezone,
            rewrite_owner_email=user.mail if IMPORT_REWRITES_OWNERSHIP else None,
            remove_attendees=IMPORT_REMOVES_ATTENDEES,
        )

    #
    # Public subscription
    #
    def enable_subscription(self, user: User, key: str) -> str:
        """Activate the public .ics subscription for a calendar and return its token.

        Generates a fresh capability token (replacing any existing one) and persists it.
        """
        source: CalendarSource = self.get_calendar(user, key)
        self._acl.check_permission(source.calendar.permissions, CalendarPermissionAction.MODIFY)
        # 64 alphanumeric chars (~381 bits): uniqueness is enforced by the UNIQUE constraint on
        # the share_token column, so no pre-check select is needed for a value this large.
        token: str = get_unique_token(SHARE_TOKEN_LENGTH)
        source.calendar.share_token = token
        source.update_calendar(source.calendar)
        return token

    def disable_subscription(self, user: User, key: str) -> None:
        """Revoke the public .ics subscription for a calendar (clears the token)."""
        source: CalendarSource = self.get_calendar(user, key)
        self._acl.check_permission(source.calendar.permissions, CalendarPermissionAction.MODIFY)
        source.calendar.share_token = None
        source.update_calendar(source.calendar)

    def export_by_share_token(self, share_token: str) -> str:
        """Return the full VCALENDAR for the calendar exposed by a public subscription token.

        No user scope: the token is the capability. Raises NOT_FOUND when the token does not
        match an active subscription (so we never reveal whether a token ever existed).
        """
        source: CalendarSource | None = self._sources.get_by_share_token(share_token)
        if source is None:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
        return self._serialize_calendar_to_ics(source, refresh_interval=PUBLIC_SUBSCRIPTION_REFRESH)

    #
    # External calendar sync
    #
    def sync_external_calendar(self, user: User, key: str) -> CalSyncResult:
        """Run a synchronous sync for an external ICS calendar."""
        # TODO: dispatch as Celery task instead of synchronous call
        source: CalendarSource = self.get_calendar(user, key)
        if source.calendar.source_type != CalendarSourceType.ICS:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        if self._cache is None:
            raise BugException("ModuleCalendar requires a cache for calendar sync")
        engine: SyncEngine = SyncEngine(sources=self._sources, cache=self._cache)
        return engine.sync(source.calendar)

    def get_sync_status(self, user: User, key: str) -> CalSyncStatus:
        """Return the sync status for an external calendar."""
        source: CalendarSource = self.get_calendar(user, key)
        if source.calendar.source_type != CalendarSourceType.ICS:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        config: dict = source.calendar.sync_config or {}
        return CalSyncStatus(
            sync_status=CalendarSyncStatus(config.get("sync_status", CalendarSyncStatus.UNDEFINED.value)),
            last_sync=config.get("last_sync"),
            sync_error=config.get("sync_error"),
        )

    #
    # Maintenance
    #
    # TODO: Implement in admin API
    def clean(self, user_uid: str | None = None, calendar_key: str | None = None) -> int:
        """Physically remove soft-deleted event and reminder rows.

        Returns the total number of rows purged. At least one of user_uid or calendar_key must
        be provided. When user_uid is given, all calendars currently owned by that user are cleaned.
        Orphaned reminder rows (soft-deleted) are purged alongside their events.
        """
        repo_event: RepositoryEvent = RepositoryEvent(self._db)
        repo_reminder: RepositoryReminder = RepositoryReminder(self._db)
        total: int = 0
        if calendar_key is not None:
            total += repo_event.purge_deleted(calendar_key)
            total += repo_reminder.purge_deleted()
        elif user_uid is not None:
            keys: list[str] = [s.calendar.require_key for s in self._sources.get_all(user_uid)]
            total += sum(repo_event.purge_deleted(k) for k in keys)
            total += repo_reminder.purge_deleted()
        return total

    #
    # FreeBusy
    #
    def get_freebusy(
        self,
        target_uid: str,
        start: datetime,
        end: datetime,
        prefs: FreeBusyPrefs,
    ) -> list[CalFreeBusyPeriod]:
        """Return merged free/busy periods for target_uid in [start, end].

        prefs must be provided by the caller (loaded from user settings).

        IMPORTANT — timezone: the off-hours computation (when prefs.busy_off_hours is True)
        uses prefs.timezone, which must be the target user's IANA timezone (SOGO_U_TIMEZONE).
        This means that "working hours" (e.g. 09:00–17:00) are interpreted in that timezone,
        not in UTC or in the requester's timezone. The caller (interface layer) is responsible
        for loading SOGO_U_TIMEZONE and setting it on FreeBusyPrefs before calling this method.
        """
        if (end - start) > timedelta(days=MAX_FREEBUSY_DAYS):
            raise RequestException(error=err.ERROR_CALENDAR_FREEBUSY_DATE_RANGE_TOO_LARGE)
        try:
            events: list[CalEvent] = self._sources.get_events(target_uid, start, end)
            return FreeBusyEngine().compute(events, start, end, prefs)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error computing freebusy for uid=%s", target_uid)
            raise RequestException(error=err.ERROR_UNKOWN) from exc
