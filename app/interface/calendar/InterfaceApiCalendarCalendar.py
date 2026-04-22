from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import CalendarContactSettings, CalendarContactSettingsObj
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalendarEventDeserializerJson import CalendarEventDeserializerJson
from app.module.calendar.serializer.CalendarEventSerializerJson import CalendarEventSerializerJson
from app.module.calendar.serializer.CalendarEventsSerializerJson import CalendarEventsSerializerJson
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.errors import ERROR_UNKOWN
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.calendar.model.CalEvent import CalEvent

_FAR_FUTURE = "9999-12-31T23:59:59Z"


class InterfaceApiCalendarCalendar:
    """
    Interface for calendar and event operations.

    Bridges the calendar API layer and ModuleCalendar.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.user: User = user
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(user_domain_settings[CalendarContactSettings.subparent])
        self.module: ModuleCalendar = ModuleCalendar(user, process_setting)
        self._events_serializer: CalendarEventsSerializerJson = CalendarEventsSerializerJson()
        self._event_serializer: CalendarEventSerializerJson = CalendarEventSerializerJson()
        self._event_deserializer: CalendarEventDeserializerJson = CalendarEventDeserializerJson()

    def get_all_calendars(self) -> tuple[dict[str, Any], int]:
        """List all calendars for the current user."""
        try:
            calendars = self.module.get_all_calendars()
            data = {
                "calendars": [self._serialize_calendar(c) for c in calendars],
                "total_count": len(calendars),
            }
            return create_api_base_response(data)
        except RequestException as ex:
            logger_api.error("get_all_calendars failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_all_calendars for user %s: %s", self.user.uid, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def get_calendar(self, key: str) -> tuple[dict[str, Any], int]:
        """Get a single calendar by its key."""
        try:
            source = self.module.get_calendar(key)
            return create_api_base_response(self._serialize_calendar(source.calendar))
        except RequestException as ex:
            logger_api.error("get_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_calendar for user %s key %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

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
            created = self.module.create_calendar(cal)
            return create_api_base_response(self._serialize_calendar(created), code=201)
        except RequestException as ex:
            logger_api.error("create_calendar failed for user %s: %s", self.user.uid, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in create_calendar for user %s: %s", self.user.uid, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def update_calendar(self, key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Update an existing calendar."""
        try:
            updated = self.module.update_calendar(key, body)
            return create_api_base_response(self._serialize_calendar(updated))
        except RequestException as ex:
            logger_api.error("update_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in update_calendar for user %s key %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def delete_calendar(self, key: str) -> tuple[dict[str, Any], int]:
        """Delete a calendar."""
        try:
            self.module.delete_calendar(key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_calendar failed for user %s key %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in delete_calendar for user %s key %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def create_event(self, calendar_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new event in the given calendar."""
        try:
            event: CalEvent = self._event_deserializer.from_dict(body)
            created = self.module.create_event(calendar_key, event)
            return create_api_base_response(self._event_serializer.to_dict(created), code=201)
        except RequestException as ex:
            logger_api.error("create_event failed for user %s calendar %s: %s", self.user.uid, calendar_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in create_event for user %s calendar %s: %s", self.user.uid, calendar_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def get_event(self, event_key: str) -> tuple[dict[str, Any], int]:
        """Get a single event by key."""
        try:
            event = self.module.get_event(event_key)
            return create_api_base_response(self._event_serializer.to_dict(event))
        except RequestException as ex:
            logger_api.error("get_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_event for user %s event %s: %s", self.user.uid, event_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def patch_event(self, event_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to an event."""
        try:
            parsed = self._event_deserializer.parse_patch_fields(body)
            updated = self.module.update_event(event_key, parsed)
            return create_api_base_response(self._event_serializer.to_dict(updated))
        except RequestException as ex:
            logger_api.error("patch_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in patch_event for user %s event %s: %s", self.user.uid, event_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def delete_event(self, event_key: str) -> tuple[dict[str, Any], int]:
        """Delete an event."""
        try:
            self.module.delete_event(event_key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_event failed for user %s event %s: %s", self.user.uid, event_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in delete_event for user %s event %s: %s", self.user.uid, event_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def get_events(self, key: str | None, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List events in a calendar, applying optional date range and search filters.

        When no dates are provided and there is no search query, defaults to the current calendar day (UTC).
        """
        try:
            start: datetime | None = query_args.get("start_date_time")
            end: datetime | None = query_args.get("end_date_time")
            search: str | None = query_args.get("search")
            if search is None and start is None and end is None:
                today = datetime.now(timezone.utc).date()
                start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
                end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
            events: list[CalEvent] = self.module.get_events(start, end, search, key)
            return create_api_base_response(self._events_serializer.to_response(events))
        except RequestException as ex:
            logger_api.error("get_events failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_events for user %s, calendar %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def get_tasks(self, key: str | None, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List VTODO tasks in a calendar with optional date range and search filters."""
        try:
            start: datetime | None = query_args.get("start_date_time")
            end: datetime | None = query_args.get("end_date_time")
            search: str | None = query_args.get("search")
            tasks: list[CalEvent] = self.module.get_tasks(start, end, search, key)
            data = {"tasks": [self._event_serializer.to_dict(t) for t in tasks], "total_count": len(tasks)}
            return create_api_base_response(data)
        except RequestException as ex:
            logger_api.error("get_tasks failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_tasks for user %s, calendar %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def create_task(self, calendar_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Create a new VTODO in the given calendar."""
        try:
            task_body = self._normalize_task_body(body)
            task: CalEvent = self._event_deserializer.from_dict(task_body)
            created = self.module.create_task(calendar_key, task)
            return create_api_base_response(self._event_serializer.to_dict(created), code=201)
        except RequestException as ex:
            logger_api.error("create_task failed for user %s calendar %s: %s", self.user.uid, calendar_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in create_task for user %s calendar %s: %s", self.user.uid, calendar_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def get_task(self, task_key: str) -> tuple[dict[str, Any], int]:
        """Get a single VTODO by key."""
        try:
            task = self.module.get_task(task_key)
            return create_api_base_response(self._event_serializer.to_dict(task))
        except RequestException as ex:
            logger_api.error("get_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_task for user %s task %s: %s", self.user.uid, task_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def patch_task(self, task_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Apply partial updates to a VTODO."""
        try:
            if "due" in body:
                body = dict(body)
                body["date_end"] = body.pop("due")
            parsed = self._event_deserializer.parse_patch_fields(body)
            updated = self.module.update_task(task_key, parsed)
            return create_api_base_response(self._event_serializer.to_dict(updated))
        except RequestException as ex:
            logger_api.error("patch_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in patch_task for user %s task %s: %s", self.user.uid, task_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    def delete_task(self, task_key: str) -> tuple[dict[str, Any], int]:
        """Delete a VTODO."""
        try:
            self.module.delete_task(task_key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("delete_task failed for user %s task %s: %s", self.user.uid, task_key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in delete_task for user %s task %s: %s", self.user.uid, task_key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

    @staticmethod
    def _normalize_task_body(body: dict[str, Any]) -> dict[str, Any]:
        """Map task API fields to CalEvent fields and fill required defaults."""
        now_iso = datetime.now(timezone.utc).isoformat()
        task_body = dict(body)
        task_body["date_start"] = task_body.get("date_start") or now_iso
        task_body["date_end"] = task_body.pop("due", None) or _FAR_FUTURE
        task_body["component_type"] = "task"
        return task_body

    @staticmethod
    def _serialize_calendar(cal: CalCalendar) -> dict[str, Any]:
        """Convert a CalCalendar to a dict suitable for API responses."""
        return {
            "key":                cal.key,
            "name":               cal.name,
            "color":              cal.color,
            "description":        cal.description,
            "timezone":           cal.timezone,
            "is_default":         cal.is_default,
            "source_type":        cal.source_type,
            "ctag":               cal.ctag,
            "share_token": cal.share_token,
            "created_at":         cal.created_at,
            "updated_at":         cal.updated_at,
        }
