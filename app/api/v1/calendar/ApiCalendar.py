from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.utils.logger.logger import logger_api
from .schemas.calendar import (
    CalendarCreateSchema,
    CalendarUpdateSchema,
    CalendarListResponseSchema,
    CalendarResponseSchema,
)
from .schemas.event import CalendarEventQueryArgsSchema, CalendarEventListResponseSchema

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("Calendar", __name__, url_prefix="/calendars")


@blp.before_request
def init_calendar_config() -> None:  # pylint: disable=missing-function-docstring
    g.inter = InterfaceApiCalendarCalendar(
        process_setting=g.process_settings,
        user_domain_settings=g.user_domain_settings,
        user=g.user,
    )


@blp.route("")
class ApiCalendarList(MethodView):
    """API to list and create calendars."""

    @blp.response(200, CalendarListResponseSchema)
    def get(self) -> ResponseReturnValue:
        """List all calendars for the current user."""
        logger_api.debug("GET /calendars user=%s", g.user.uid)
        return g.inter.get_all_calendars()

    @blp.arguments(CalendarCreateSchema)
    @blp.response(200, CalendarResponseSchema)
    def post(self, body: dict) -> ResponseReturnValue:
        """Create a new calendar."""
        logger_api.debug("POST /calendars user=%s body=%s", g.user.uid, body)
        return g.inter.create_calendar(body)


@blp.route("/<string:key>")
class ApiCalendarDetail(MethodView):
    """API to retrieve, update and delete a single calendar."""

    @blp.response(200, CalendarResponseSchema)
    def get(self, key: str) -> ResponseReturnValue:
        """Get a calendar by its key."""
        logger_api.debug("GET /calendars/%s user=%s", key, g.user.uid)
        return g.inter.get_calendar(key)

    @blp.arguments(CalendarUpdateSchema)
    @blp.response(200, CalendarResponseSchema)
    def patch(self, body: dict, key: str) -> ResponseReturnValue:
        """Update a calendar."""
        logger_api.debug("PATCH /calendars/%s user=%s body=%s", key, g.user.uid, body)
        return g.inter.update_calendar(key, body)

    @blp.response(200, CalendarResponseSchema)
    def delete(self, key: str) -> ResponseReturnValue:
        """Delete a calendar."""
        logger_api.debug("DELETE /calendars/%s user=%s", key, g.user.uid)
        return g.inter.delete_calendar(key)


@blp.route("/<string:key>/events")
class ApiCalendarEventList(MethodView):
    """API to list events in a specific calendar."""

    @blp.arguments(CalendarEventQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarEventListResponseSchema, example=CalendarEventListResponseSchema.example())
    def get(self, query_args: dict, key: str) -> ResponseReturnValue:
        """List events in a calendar, with optional date range and search."""
        logger_api.debug("GET /calendars/%s/events args=%s", key, query_args)
        return g.inter.get_calendar_events(key, query_args)
