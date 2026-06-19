from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.utils.api.external_url import build_external_url

from app.config.settings.DomainSettings import CalendarContactSettings, CalendarContactSettingsObj
from app.config.settings.UserSettings import UserCalendarGeneralSettings, UserGeneralSettings
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.freebusy.FreeBusyEngine import FreeBusyPrefs
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalendarUser import CalendarUser
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.CalFreeBusyResult import CalFreeBusyResult
from app.module.calendar.serializer.CalEventDeserializerDict import CalEventDeserializerDict
from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict
from app.module.calendar.serializer.CalEventsSerializerDict import CalEventsSerializerDict
from app.module.calendar.serializer.CalCalendarSerializerDict import CalCalendarSerializerDict
from app.module.calendar.serializer.CalCalendarsSerializerList import CalCalendarsSerializerList
from app.module.calendar.serializer.CalEventReminderSerializerDict import CalEventReminderSerializerDict
from app.module.calendar.serializer.CalFreeBusyResultSerializerDict import CalFreeBusyResultSerializerDict
from app.module.calendar.serializer.CalSyncResultSerializerDict import CalSyncResultSerializerDict
from app.module.calendar.serializer.CalSyncStatusSerializerDict import CalSyncStatusSerializerDict
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.service import sogo_agent, sogo_cache
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.errors import ERROR_CALENDAR_JSON_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.utils.strings import get_domain_from_mail
from app.auth.User import User
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.source.CalendarSource import CalendarSource


class InterfaceApiCalendarCalendar:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Interface for all calendar operations (calendars, events, tasks, freebusy, reminders, external sync)."""

    _PUBLIC_SUBSCRIPTION_ENDPOINT: str = "user#Calendar.v1_Calendar.Calendar.ApiCalendarPublicSubscription"

    @staticmethod
    def _add_months(dt: datetime, months: int) -> datetime:
        """Return dt shifted by the given number of months, clamping to the last day if needed."""
        total = dt.month - 1 + months
        year = dt.year + total // 12
        month = total % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.user: User = user
        self._process_setting: ProcessSetting = process_setting
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(user_domain_settings[CalendarContactSettings.subparent])
        self.module: ModuleCalendar = ModuleCalendar(process_setting, cache=sogo_cache(), agent=sogo_agent())
        self._user_module: ModuleUserProfile = ModuleUserProfile(process_setting, user_domain_settings)
        self._events_serializer: CalEventsSerializerDict = CalEventsSerializerDict()
        self._event_serializer: CalEventSerializerDict = CalEventSerializerDict()
        self._event_deserializer: CalEventDeserializerDict = CalEventDeserializerDict()
        self._calendar_serializer: CalCalendarSerializerDict = CalCalendarSerializerDict()
        self._calendars_serializer: CalCalendarsSerializerList = CalCalendarsSerializerList()
        self._freebusy_serializer: CalFreeBusyResultSerializerDict = CalFreeBusyResultSerializerDict()
        self._reminder_serializer: CalEventReminderSerializerDict = CalEventReminderSerializerDict()
        self._sync_result_serializer: CalSyncResultSerializerDict = CalSyncResultSerializerDict()
        self._sync_status_serializer: CalSyncStatusSerializerDict = CalSyncStatusSerializerDict()

    def _calendar_user_for(self, calendar_key: str) -> CalendarUser:
        """Build a CalendarUser by resolving the owner from the calendar's user_uid."""
        source: CalendarSource = self.module.get_calendar(self.user, calendar_key)
        owner_uid: str = source.calendar.user_uid
        if owner_uid == self.user.uid:
            return CalendarUser(user=self.user, owner=self.user)
        owner: User = User(uid=owner_uid)
        owner.mail = owner_uid
        self._user_module.get_user_profile(owner)
        return CalendarUser(user=self.user, owner=owner)

    def _public_url(self, share_token: str | None) -> str | None:
        """Build the absolute public subscription URL for a calendar, or None when inactive."""
        if not share_token:
            return None
        return build_external_url(
            self._PUBLIC_SUBSCRIPTION_ENDPOINT,
            self._process_setting.SOGO_P_PUBLIC_BASE_URL,
            token=share_token,
        )

    #
    # Calendars
    #
    def get_all_calendars(self, source_type: str | None = None) -> tuple[dict[str, Any], int]:
        """List calendars for the current user, optionally filtered by source_type."""
        try:
            calendars: list[CalCalendar] = self.module.get_all_calendars(self.user)
            if source_type is not None:
                calendars = [c for c in calendars if c.source_type.value == source_type]
            serialized: list[dict[str, Any]] = self._calendars_serializer.serialize(calendars)
            # public_url is an API-level value (derived via url_for) injected after serialization;
            # the order matches since CalCalendarsSerializerList preserves the input order.
            for index, cal in enumerate(calendars):
                serialized[index]["public_url"] = self._public_url(cal.share_token)
            return create_api_base_response({"calendars": serialized, "total_count": len(calendars)})
        except RequestException as ex:
            logger_api.error("get_all_calendars failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def get_calendar(self, key: str) -> tuple[dict[str, Any], int]:
        """Get a single calendar by its key."""
        try:
            source: CalendarSource = self.module.get_calendar(self.user, key)
            cal_dict: dict[str, Any] = self._calendar_serializer.serialize(source.calendar)
            cal_dict["public_url"] = self._public_url(source.calendar.share_token)
            return create_api_base_response(cal_dict)
        except RequestException as ex:
            logger_api.error("get_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_calendar(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new calendar.

        When the caller does not supply a timezone, the calendar inherits the user's own
        timezone (``SOGO_U_TIMEZONE``). This makes the calendar timezone a sensible default
        anchor for floating-time events imported later.
        """
        try:
            default_type_raw: str | None = body.get("default_type")
            cal: CalCalendar = CalCalendar(
                user_uid=self.user.uid,
                name=body["name"],
                color=body.get("color"),
                description=body.get("description"),
                timezone=body.get("timezone") or self._user_timezone(self.user.uid),
                source_type=CalendarSourceType.LOCAL,
                include_in_freebusy=body.get("include_in_freebusy", True),
                default_event_duration_min=body.get("default_event_duration_min"),
                default_alarm_duration_min=body.get("default_alarm_duration_min"),
                default_type=EventVisibility(default_type_raw) if default_type_raw else None,
            )
            created: CalCalendar = self.module.create_calendar(self.user, cal)
            return create_api_base_response(self._calendar_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_calendar failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def update_calendar(self, key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Update an existing calendar."""
        try:
            updates: dict[str, Any] = self._normalize_calendar_updates(body)
            updated: CalCalendar = self.module.update_calendar(self.user, key, updates)
            return create_api_base_response(self._calendar_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("update_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def delete_calendar(self, key: str) -> tuple[dict[str, Any], int]:
        """Delete a calendar."""
        try:
            self.module.delete_calendar(self.user, key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Events
    #
    def create_event(self, calendar_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new event in the given calendar."""
        try:
            event: CalEvent = self._event_deserializer.deserialize(body)
            organizer: CalOrganizer = CalOrganizer(email=self.user.mail)
            created: CalEvent = self.module.create_event(CalendarUser(user=self.user, owner=self.user), calendar_key, event, organizer)
            return create_api_base_response(self._event_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_event failed for user %s calendar %s: %s", self.user.uid, calendar_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse event body for user %s calendar %s: %s", self.user.uid, calendar_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def get_event(self, event_key: str) -> tuple[dict[str, Any], int]:
        """Get a single event by key."""
        try:
            event: CalEvent = self.module.get_event(CalendarUser(user=self.user, owner=self.user), event_key)
            return create_api_base_response(self._event_serializer.serialize(event))
        except RequestException as ex:
            logger_api.error("get_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)

    def patch_event(self, event_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to an event."""
        try:
            existing: CalEvent = self.module.get_event(CalendarUser(user=self.user, owner=self.user), event_key)
            event_update: CalEvent = self._event_deserializer.deserialize_with_update(existing, body)
            organizer: CalOrganizer = CalOrganizer(email=self.user.mail)
            updated: CalEvent = self.module.update_event(CalendarUser(user=self.user, owner=self.user), event_key, event_update, organizer)
            return create_api_base_response(self._event_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("patch_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse patch body for user %s event %s: %s", self.user.uid, event_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def set_attendance_status(self, event_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Set the current user's attendance status for an event.

        :param event_key: Opaque key of the event in the user's calendar.
        :param body: Validated request body with ``status`` (accepted / declined / tentative / delegated).
        :return: API envelope with the updated event, plus HTTP status code.
        """
        try:
            attendance: AttendeeStatus = AttendeeStatus(body["status"])
            recurrence_id: datetime | None = body.get("recurrence_id")
            updated: CalEvent = self.module.set_attendance_status(CalendarUser(user=self.user, owner=self.user), event_key, attendance, recurrence_id)
            return create_api_base_response(self._event_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("set_attendance_status failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)
        except ValueError as exc:
            logger_api.error("Invalid attendance status value for event %s: %s", event_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def delete_event(self, event_key: str) -> tuple[dict[str, Any], int]:
        """Delete an event."""
        try:
            self.module.delete_event(CalendarUser(user=self.user, owner=self.user), event_key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)

    def get_events(self, key: str | None, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List events in a calendar, applying optional date range and search filters.

        When no dates are provided and there is no search query, defaults to the current calendar day (UTC).

        :param key: Calendar key, or None to query all user calendars.
        :param query_args: Parsed query arguments: ``start_date_time``, ``end_date_time``, ``search`` (all optional).
        :return: API envelope with ``events`` list and ``total_count``, plus HTTP status code.
        """
        try:
            start: datetime | None = query_args.get("start_date_time")
            end: datetime | None = query_args.get("end_date_time")
            search: str | None = query_args.get("search")
            if search is None and start is None and end is None:
                today = datetime.now(timezone.utc).date()
                start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
                end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
            events: list[CalEvent] = self.module.get_events(CalendarUser(user=self.user, owner=self.user), start, end, search, key)
            event_list: list[dict[str, Any]] = self._events_serializer.serialize(events)
            return create_api_base_response({"events": event_list, "total_count": len(event_list)})
        except RequestException as ex:
            logger_api.error("get_events failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Tasks
    #
    def get_tasks(self, key: str | None, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List VTODO tasks in a calendar with optional date range and search filters.

        When no date bounds are provided, defaults to 3 months ago -> 9 months ahead.

        :param key: Calendar key, or None to query all user calendars.
        :type key: str | None
        :param query_args: Parsed query arguments: ``start_date_time``, ``end_date_time``, ``search`` (all optional).
        :type query_args: dict
        :return: API envelope with ``tasks`` list and ``total_count``, plus HTTP status code.
        :rtype: tuple[dict, int]
        """
        try:
            now = datetime.now(timezone.utc)
            start: datetime = query_args.get("start_date_time") or self._add_months(now, -3)
            end: datetime = query_args.get("end_date_time") or self._add_months(now, 9)
            search: str | None = query_args.get("search")
            tasks: list[CalEvent] = self.module.get_tasks(CalendarUser(user=self.user, owner=self.user), start, end, search, key)
            task_list: list[dict[str, Any]] = [self._serialize_task(t) for t in tasks]
            return create_api_base_response({"tasks": task_list, "total_count": len(task_list)})
        except RequestException as ex:
            logger_api.error("get_tasks failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_task(self, calendar_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new VTODO in the given calendar."""
        try:
            task_body: dict[str, Any] = self._normalize_task_body(body)
            task: CalEvent = self._event_deserializer.deserialize(task_body)
            created: CalEvent = self.module.create_task(CalendarUser(user=self.user, owner=self.user), calendar_key, task)
            return create_api_base_response(self._serialize_task(created), code=201)
        except RequestException as ex:
            logger_api.error("create_task failed for user %s calendar %s: %s", self.user.uid, calendar_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse task body for user %s calendar %s: %s", self.user.uid, calendar_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def get_task(self, task_key: str) -> tuple[dict[str, Any], int]:
        """Get a single VTODO by key."""
        try:
            task: CalEvent = self.module.get_task(CalendarUser(user=self.user, owner=self.user), task_key)
            return create_api_base_response(self._serialize_task(task))
        except RequestException as ex:
            logger_api.error("get_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)

    def patch_task(self, task_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to a VTODO."""
        try:
            if "date_due" in body:
                body = dict(body)
                body["date_end"] = body.pop("date_due")
            existing: CalEvent = self.module.get_task(CalendarUser(user=self.user, owner=self.user), task_key)
            task_update: CalEvent = self._event_deserializer.deserialize_with_update(existing, body)
            updated: CalEvent = self.module.update_task(CalendarUser(user=self.user, owner=self.user), task_key, task_update)
            return create_api_base_response(self._serialize_task(updated))
        except RequestException as ex:
            logger_api.error("patch_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse patch body for user %s task %s: %s", self.user.uid, task_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def delete_task(self, task_key: str) -> tuple[dict[str, Any], int]:
        """Delete a VTODO."""
        try:
            self.module.delete_task(CalendarUser(user=self.user, owner=self.user), task_key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Reminders
    #
    def get_reminders(self, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Return currently active reminders for the current user."""
        try:
            method_str: str | None = query_args.get("method")
            method: ReminderMethod | None = ReminderMethod(method_str) if method_str else None
            lookahead: int = query_args.get("lookahead", 0)
            reminders: list[CalEventReminder] = self.module.get_reminders(
                calendar_user=CalendarUser(user=self.user, owner=self.user), method=method, lookahead_minutes=lookahead,
            )
            reminder_list: list[dict[str, Any]] = [self._reminder_serializer.serialize(r) for r in reminders]
            return create_api_base_response({"reminders": reminder_list, "total_count": len(reminder_list)})
        except RequestException as ex:
            logger_api.error("get_reminders failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)
        except ValueError as exc:
            logger_api.error("Invalid reminder query for user %s: %s", self.user.uid, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    #
    # FreeBusy
    #
    def _user_timezone(self, uid: str) -> str:
        """Return the user's IANA timezone (``SOGO_U_TIMEZONE``), defaulting to UTC."""
        raw_gen: dict = self._user_module.get_partial_user_preferences(uid, UserGeneralSettings.subparent.lower())
        return raw_gen.get(UserGeneralSettings.subparent, {}).get("SOGO_U_TIMEZONE", "UTC")

    def _load_freebusy_prefs(self, target_uid: str) -> FreeBusyPrefs:
        """Load FreeBusy preferences for target_uid from user settings."""
        raw_cal: dict = self._user_module.get_partial_user_preferences(target_uid, UserCalendarGeneralSettings.subparent.lower())
        cal_prefs: dict = raw_cal.get(UserCalendarGeneralSettings.subparent, {})
        return FreeBusyPrefs(
            busy_off_hours=cal_prefs.get("SOGO_U_BUSY_OFF_HOURS", False),
            workday_start=cal_prefs.get("SOGO_U_WORKDAY_START_TIME", "09:00"),
            workday_end=cal_prefs.get("SOGO_U_WORKDAY_END_TIME", "18:00"),
            timezone=self._user_timezone(target_uid),
        )

    def _compute_freebusy(self, target_uids: list[str], start: datetime, end: datetime) -> dict:
        """Compute free/busy periods for each uid and return a dict keyed by uid."""
        periods_by_uid = {}
        for uid in target_uids:
            prefs = self._load_freebusy_prefs(uid)
            periods_by_uid[uid] = self.module.get_freebusy(uid, start, end, prefs)
        return periods_by_uid

    def get_freebusy(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Compute free/busy periods for a list of target users and return them as JSON.

        :param body: Validated request body with ``target_uids`` (list of user UIDs), ``start`` and ``end`` datetimes.
        :type body: dict
        :return: API envelope with free/busy periods keyed by UID, plus HTTP status code.
        :rtype: tuple[dict, int]
        """
        try:
            target_uids: list[str] = body["target_uids"]
            start: datetime = body["start"]
            end: datetime = body["end"]
            periods_by_uid = self._compute_freebusy(target_uids, start, end)
            result = CalFreeBusyResult(periods_by_uid=periods_by_uid, start=start, end=end)
            return create_api_base_response(self._freebusy_serializer.serialize(result))
        except RequestException as ex:
            logger_api.error("get_freebusy failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    #
    # External calendars
    #
    def create_external_calendar(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new external ICS calendar subscription via the common create_calendar flow.

        :param body: Validated request body with ``name``, ``url``, optional ``color`` and ``sync_interval_minutes``.
        :type body: dict
        :return: API envelope with the created calendar, plus HTTP status code.
        :rtype: tuple[dict, int]
        """
        try:
            cal: CalCalendar = CalCalendar(
                user_uid=self.user.uid,
                name=body["name"],
                color=body.get("color"),
                source_type=CalendarSourceType.ICS,
                sync_config={
                    "url": body["url"],
                    "sync_interval_minutes": body.get("sync_interval_minutes", 60),
                    "sync_status": CalendarSyncStatus.PENDING.value,
                },
            )
            created: CalCalendar = self.module.create_calendar(self.user, cal)
            return create_api_base_response(self._calendar_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_external_calendar failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def sync_external_calendar(self, key: str) -> tuple[dict[str, Any], int]:
        """Trigger a sync for an external ICS calendar."""
        try:
            result = self.module.sync_external_calendar(self.user, key)
            return create_api_base_response(self._sync_result_serializer.serialize(result))
        except RequestException as ex:
            logger_api.error("sync_external_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def get_sync_status(self, key: str) -> tuple[dict[str, Any], int]:
        """Return the sync status for an external calendar."""
        try:
            status = self.module.get_sync_status(self.user, key)
            return create_api_base_response(self._sync_status_serializer.serialize(status))
        except RequestException as ex:
            logger_api.error("get_sync_status failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Import / Export
    #
    def export_calendar(self, key: str, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Enqueue an ICS export as an Agent job and return its ``job_id``.

        The export always runs in the background: the response carries a
        ``job_id`` (202). The caller polls ``GET /jobs/<job_id>`` until SUCCESS
        then fetches ``GET /jobs/<job_id>/result``.

        :param key: Opaque calendar key.
        :param query_args: Validated query string - ``start_date_time`` /
            ``end_date_time`` bounds.
        :return: API envelope with ``{"job_id": "..."}`` and status 202, or the
            standard error envelope on failure.
        """
        try:
            date_start: datetime | None = query_args.get("start_date_time")
            date_end: datetime | None = query_args.get("end_date_time")
            job_id: str = self.module.export_calendar(
                self.user, key, date_start=date_start, date_end=date_end,
            )
            return create_api_base_response({"job_id": job_id}, code=202)
        except RequestException as ex:
            logger_api.error("export_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def import_calendar(self, key: str, ics_bytes: bytes) -> tuple[dict[str, Any], int]:
        """Enqueue an ICS import as an Agent job and return its ``job_id``.

        The import always runs in the background: the response carries a ``job_id``
        (202). The caller polls ``GET /jobs/<job_id>`` until SUCCESS; the import
        counters are then available in the job's ``result``.

        :param key: Opaque calendar key.
        :param ics_bytes: Raw uploaded VCALENDAR bytes.
        :return: API envelope with ``{"job_id": "..."}`` and status 202, or the
            standard error envelope on failure.
        """
        try:
            job_id: str = self.module.import_calendar(self.user, key, ics_bytes)
            return create_api_base_response({"job_id": job_id}, code=202)
        except RequestException as ex:
            logger_api.error("import_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    #
    # Public subscription
    #
    def enable_subscription(self, key: str) -> tuple[dict[str, Any], int]:
        """Activate the public .ics subscription and return its token and absolute URL.

        The module refuses when the user's domain disables the public link feature
        (``SOGO_D_CALENDAR_PUBLIC_LINK_ENABLED``).
        """
        try:
            token: str = self.module.enable_subscription(self.user, key, self.settings)
            return create_api_base_response({"share_token": token, "public_url": self._public_url(token)})
        except RequestException as ex:
            logger_api.error("enable_subscription failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def disable_subscription(self, key: str) -> tuple[dict[str, Any], int]:
        """Revoke the public .ics subscription and return the updated calendar."""
        try:
            self.module.disable_subscription(self.user, key)
            source: CalendarSource = self.module.get_calendar(self.user, key)
            cal_dict: dict[str, Any] = self._calendar_serializer.serialize(source.calendar)
            cal_dict["public_url"] = self._public_url(source.calendar.share_token)
            return create_api_base_response(cal_dict)
        except RequestException as ex:
            logger_api.error("disable_subscription failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def export_public_calendar(self, token: str) -> tuple[str, int, dict[str, str]] | tuple[dict[str, Any], int]:
        """Serve the full calendar as ``text/calendar`` for a public subscription token.

        Unauthenticated path - the token is the capability. Returns the standard error
        envelope (404) when the token does not match an active subscription, or when the
        calendar owner's domain disables public links. The caller being anonymous, the
        relevant domain settings are the owner's ones: the owner is resolved from the token
        first, then their domain settings are loaded and handed to the export.
        """
        try:
            owner_uid: str = self.module.get_calendar_by_share_token(token).user_uid
            owner_settings: CalendarContactSettingsObj = self._calendar_settings_by_uid(owner_uid)
            ics_text: str = self.module.export_by_share_token(token, owner_settings)
            return ics_text, 200, {"Content-Type": "text/calendar; charset=utf-8"}
        except RequestException as ex:
            # An unknown token is a normal 404, not an anomaly - no log (and never log the
            # token itself, it is a secret capability).
            return create_api_base_response(None, ex.error)

    def _calendar_settings_by_uid(self, user_uid: str) -> CalendarContactSettingsObj:
        """Typed calendar domain settings of the domain owning ``user_uid``.

        Used by the anonymous public fetch, where the relevant domain is the calendar owner's
        one (not the caller's). A domainless uid resolves like an unknown domain:
        get_one_domain_setting falls back to the default domain settings when no row matches.
        """
        config_module: ModuleAdminConfig = ModuleAdminConfig(self._process_setting)
        domain: str = get_domain_from_mail(user_uid) or ""
        raw: dict = config_module.get_one_domain_setting(domain)["settings"]
        return CalendarContactSettingsObj(raw[CalendarContactSettings.subparent])

    @staticmethod
    def _normalize_calendar_updates(body: dict[str, Any]) -> dict[str, Any]:
        """Convert API-format calendar update fields into model values (default_type string -> enum)."""
        updates: dict[str, Any] = dict(body)
        if "default_type" in updates:
            raw = updates["default_type"]
            updates["default_type"] = EventVisibility(raw) if raw else None
        return updates

    @staticmethod
    def _normalize_task_body(body: dict[str, Any]) -> dict[str, Any]:
        """Map task API fields to CalEvent fields and fill required defaults."""
        now_iso: str = datetime.now(timezone.utc).isoformat()
        task_body: dict[str, Any] = dict(body)
        task_body["date_start"] = task_body.get("date_start") or now_iso
        task_body["date_end"] = task_body.pop("date_due", None)
        task_body["component_type"] = "task"
        return task_body

    def _serialize_task(self, task: CalEvent) -> dict[str, Any]:
        """Serialize a VTODO: the event serializer emits date_end, surfaced here as ``date_due``.

        Inverse of :meth:`_normalize_task_body`. A task without a due date has date_end=None,
        so ``date_due`` comes out null.
        """
        result: dict[str, Any] = self._event_serializer.serialize(task)
        result["date_due"] = result.pop("date_end", None)
        return result
