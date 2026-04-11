from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import CalendarContactSettings, CalendarContactSettingsObj
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.serializer.CalendarEventsSerializerJson import CalendarEventsSerializerJson
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.errors import ERROR_UNKOWN
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.calendar.model.CalEvent import CalEvent


class InterfaceApiCalendarCalendar:
    """
    Interface for calendar operations.

    Bridges the calendar API layer and ModuleCalendar.
    Handles user-facing operations: list, create, retrieve, update, delete calendars.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.user: User = user
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(user_domain_settings[CalendarContactSettings.subparent])
        self.module: ModuleCalendar = ModuleCalendar(user)
        self._events_serializer: CalendarEventsSerializerJson = CalendarEventsSerializerJson()

    def get_calendar_events(self, calendar_id: str, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List events in a calendar, applying optional date range and search filters."""
        try:
            start: datetime | None = query_args.get("start_date_time")
            end: datetime | None = query_args.get("end_date_time")
            search: str | None = query_args.get("search")
            events: list[CalEvent] = self.module.get_calendar_events(calendar_id, start, end, search)
            return create_api_base_response(self._events_serializer.to_response(events))
        except RequestException as ex:
            logger_api.error("get_calendar_events failed for user %s, calendar %s: %s", self.user.uid, calendar_id, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_calendar_events for user %s, calendar %s: %s", self.user.uid, calendar_id, exc)
            return create_api_base_response(None, ERROR_UNKOWN)
