from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import CalendarContactSettings, CalendarContactSettingsObj
from app.config.settings.UserSettings import UserCalendarGeneralSettings, UserGeneralSettings
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.freebusy.FreeBusyEngine import FreeBusyPrefs
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalFreeBusyResult import CalFreeBusyResult
from app.module.calendar.serializer.CalendarEventDeserializerDict import CalendarEventDeserializerDict
from app.module.calendar.serializer.CalendarEventSerializerDict import CalendarEventSerializerDict
from app.module.calendar.serializer.CalendarEventsSerializerDict import CalendarEventsSerializerDict
from app.module.calendar.serializer.CalendarSerializerDict import CalendarSerializerDict
from app.module.calendar.serializer.CalendarsSerializerList import CalendarsSerializerList
from app.module.calendar.serializer.FreeBusySerializerDict import FreeBusySerializerDict
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.errors import ERROR_CALENDAR_JSON_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.calendar.model.CalEvent import CalEvent

_FAR_FUTURE = "9999-12-31T23:59:59Z"


class InterfaceApiCalendarCalendar:  # pylint: disable=too-many-instance-attributes
    """
    Interface for calendar and event operations.

    Bridges the calendar API layer and ModuleCalendar.
    """

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
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(user_domain_settings[CalendarContactSettings.subparent])
        self.module: ModuleCalendar = ModuleCalendar(process_setting)
        self._user_module: ModuleUserProfile = ModuleUserProfile(process_setting, user_domain_settings)
        self._events_serializer: CalendarEventsSerializerDict = CalendarEventsSerializerDict()
        self._event_serializer: CalendarEventSerializerDict = CalendarEventSerializerDict()
        self._event_deserializer: CalendarEventDeserializerDict = CalendarEventDeserializerDict()
        self._calendar_serializer: CalendarSerializerDict = CalendarSerializerDict()
        self._calendars_serializer: CalendarsSerializerList = CalendarsSerializerList()
        self._freebusy_serializer: FreeBusySerializerDict = FreeBusySerializerDict()

    def get_all_calendars(self) -> tuple[dict[str, Any], int]:
        """List all calendars for the current user."""
        try:
            calendars = self.module.get_all_calendars(self.user)
            return create_api_base_response({"calendars": self._calendars_serializer.serialize(calendars), "total_count": len(calendars)})
        except RequestException as ex:
            logger_api.error("get_all_calendars failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def get_calendar(self, key: str) -> tuple[dict[str, Any], int]:
        """Get a single calendar by its key."""
        try:
            source = self.module.get_calendar(self.user, key)
            return create_api_base_response(self._calendar_serializer.serialize(source.calendar))
        except RequestException as ex:
            logger_api.error("get_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_calendar(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new calendar."""
        try:
            cal = CalCalendar(
                user_uid=self.user.uid,
                name=body["name"],
                color=body.get("color"),
                description=body.get("description"),
                timezone=body.get("timezone", "UTC"),
            )
            created = self.module.create_calendar(self.user, cal)
            return create_api_base_response(self._calendar_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_calendar failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)

    def update_calendar(self, key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Update an existing calendar."""
        try:
            updated = self.module.update_calendar(self.user, key, body)
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

    def create_event(self, calendar_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new event in the given calendar."""
        try:
            event: CalEvent = self._event_deserializer.deserialize(body)
            created = self.module.create_event(self.user, calendar_key, event)
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
            event = self.module.get_event(self.user, event_key)
            return create_api_base_response(self._event_serializer.serialize(event))
        except RequestException as ex:
            logger_api.error("get_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)

    def patch_event(self, event_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to an event."""
        try:
            parsed = self._event_deserializer.parse_patch_fields(body)
            updated = self.module.update_event(self.user, event_key, parsed)
            return create_api_base_response(self._event_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("patch_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse patch body for user %s event %s: %s", self.user.uid, event_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def delete_event(self, event_key: str) -> tuple[dict[str, Any], int]:
        """Delete an event."""
        try:
            self.module.delete_event(self.user, event_key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)

    def get_events(self, key: str | None, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List events in a calendar, applying optional date range and search filters.

        When no dates are provided and there is no search query, defaults to the current calendar day (UTC).

        :param key: Calendar key, or None to query all user calendars.
        :type key: str | None
        :param query_args: Parsed query arguments: ``start_date_time``, ``end_date_time``, ``search`` (all optional).
        :type query_args: dict
        :return: API envelope with ``events`` list and ``total_count``, plus HTTP status code.
        :rtype: tuple[dict, int]
        """
        try:
            start: datetime | None = query_args.get("start_date_time")
            end: datetime | None = query_args.get("end_date_time")
            search: str | None = query_args.get("search")
            if search is None and start is None and end is None:
                today = datetime.now(timezone.utc).date()
                start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
                end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
            events: list[CalEvent] = self.module.get_events(self.user, start, end, search, key)
            event_list = self._events_serializer.serialize(events)
            return create_api_base_response({"events": event_list, "total_count": len(event_list)})
        except RequestException as ex:
            logger_api.error("get_events failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def get_tasks(self, key: str | None, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List VTODO tasks in a calendar with optional date range and search filters.

        When no date bounds are provided, defaults to 3 months ago → 9 months ahead.

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
            tasks: list[CalEvent] = self.module.get_tasks(self.user, start, end, search, key)
            task_list = self._events_serializer.serialize(tasks)
            return create_api_base_response({"tasks": task_list, "total_count": len(task_list)})
        except RequestException as ex:
            logger_api.error("get_tasks failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)

    def create_task(self, calendar_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new VTODO in the given calendar."""
        try:
            task_body = self._normalize_task_body(body)
            task: CalEvent = self._event_deserializer.deserialize(task_body)
            created = self.module.create_task(self.user, calendar_key, task)
            return create_api_base_response(self._event_serializer.serialize(created), code=201)
        except RequestException as ex:
            logger_api.error("create_task failed for user %s calendar %s: %s", self.user.uid, calendar_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse task body for user %s calendar %s: %s", self.user.uid, calendar_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def get_task(self, task_key: str) -> tuple[dict[str, Any], int]:
        """Get a single VTODO by key."""
        try:
            task = self.module.get_task(self.user, task_key)
            return create_api_base_response(self._event_serializer.serialize(task))
        except RequestException as ex:
            logger_api.error("get_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)

    def patch_task(self, task_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to a VTODO."""
        try:
            if "due" in body:
                body = dict(body)
                body["date_end"] = body.pop("due")
            parsed = self._event_deserializer.parse_patch_fields(body)
            updated = self.module.update_task(self.user, task_key, parsed)
            return create_api_base_response(self._event_serializer.serialize(updated))
        except RequestException as ex:
            logger_api.error("patch_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)
        except (ValueError, KeyError) as exc:
            logger_api.error("Failed to parse patch body for user %s task %s: %s", self.user.uid, task_key, exc)
            return create_api_base_response(None, ERROR_CALENDAR_JSON_PARSE_FAILED)

    def delete_task(self, task_key: str) -> tuple[dict[str, Any], int]:
        """Delete a VTODO."""
        try:
            self.module.delete_task(self.user, task_key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)

    def _load_freebusy_prefs(self, target_uid: str) -> FreeBusyPrefs:
        """Load FreeBusy preferences for target_uid from user settings."""
        raw_cal = self._user_module.get_partial_user_preferences(target_uid, UserCalendarGeneralSettings.subparent.lower())
        cal_prefs = raw_cal.get(UserCalendarGeneralSettings.subparent, {})
        raw_gen = self._user_module.get_partial_user_preferences(target_uid, UserGeneralSettings.subparent.lower())
        user_tz = raw_gen.get(UserGeneralSettings.subparent, {}).get("SOGO_U_TIMEZONE", "UTC")
        return FreeBusyPrefs(
            busy_off_hours=cal_prefs.get("SOGO_U_BUSY_OFF_HOURS", False),
            workday_start=cal_prefs.get("SOGO_U_WORKDAY_START_TIME", "09:00"),
            workday_end=cal_prefs.get("SOGO_U_WORKDAY_END_TIME", "18:00"),
            timezone=user_tz,
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

    @staticmethod
    def _normalize_task_body(body: dict[str, Any]) -> dict[str, Any]:
        """Map task API fields to CalEvent fields and fill required defaults."""
        now_iso = datetime.now(timezone.utc).isoformat()
        task_body = dict(body)
        task_body["date_start"] = task_body.get("date_start") or now_iso
        task_body["date_end"] = task_body.pop("due", None) or _FAR_FUTURE
        task_body["component_type"] = "task"
        return task_body
