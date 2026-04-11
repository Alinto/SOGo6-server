from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.utils.logger.logger import logger_api
from .schemas.event import CalendarEventQueryArgsSchema, CalendarEventListResponseSchema

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("Calendar", __name__, url_prefix="/calendars")


@blp.before_request
def init_calendar_config() -> None:  # pylint: disable=missing-function-docstring
    process: ProcessSetting = g.process_settings
    user_domain_settings: dict = g.user_domain_settings
    user: User = g.user

    g.inter = InterfaceApiCalendarCalendar(
        process_setting=process,
        user_domain_settings=user_domain_settings,
        user=user,
    )


@blp.route("/<string:calendar_id>/events")
class ApiCalendarEventList(MethodView):
    """API to list events in a specific calendar."""

    @blp.arguments(CalendarEventQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarEventListResponseSchema, example=CalendarEventListResponseSchema.example())
    def get(self, query_args: dict, calendar_id: str) -> ResponseReturnValue:
        """List events in a calendar, with optional date range, and search.

        :param query_args: Validated query parameters (start_date_time, end_date_time, search).
        :param calendar_id: The calendar identifier (hash).
        """
        logger_api.debug("GET /calendars/%s/events args=%s", calendar_id, query_args)
        return g.inter.get_calendar_events(calendar_id, query_args)
