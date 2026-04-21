from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import CalendarContactSettings, CalendarContactSettingsObj
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
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
    Interface for calendar and event operations.

    Bridges the calendar API layer and ModuleCalendar.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.user: User = user
        self.settings: CalendarContactSettingsObj = CalendarContactSettingsObj(user_domain_settings[CalendarContactSettings.subparent])
        self.module: ModuleCalendar = ModuleCalendar(user, process_setting)
        self._events_serializer: CalendarEventsSerializerJson = CalendarEventsSerializerJson()

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
            cal = self.module.get_calendar(key)
            return create_api_base_response(self._serialize_calendar(cal))
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
            return create_api_base_response(self._serialize_calendar(created))
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

    def get_calendar_events(self, key: str, query_args: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """List events in a calendar, applying optional date range and search filters."""
        try:
            start: datetime | None = query_args.get("start_date_time")
            end: datetime | None = query_args.get("end_date_time")
            search: str | None = query_args.get("search")
            events: list[CalEvent] = self.module.get_calendar_events(key, start, end, search)
            return create_api_base_response(self._events_serializer.to_response(events))
        except RequestException as ex:
            logger_api.error("get_calendar_events failed for user %s, calendar %s: %s", self.user.uid, key, ex)
            return create_api_base_response(None, ex.error)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger_api.error("Unexpected error in get_calendar_events for user %s, calendar %s: %s", self.user.uid, key, exc)
            return create_api_base_response(None, ERROR_UNKOWN)

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
