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
from .schemas.event import (
    CalendarEventQueryArgsSchema,
    CalendarEventListResponseSchema,
    CalendarEventCreateSchema,
    CalendarEventPatchSchema,
    CalendarEventResponseSchema,
)
from .schemas.task import (
    CalendarTaskQueryArgsSchema,
    CalendarTaskListResponseSchema,
    CalendarTaskCreateSchema,
    CalendarTaskPatchSchema,
    CalendarTaskResponseSchema,
)

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("Calendar", __name__, url_prefix="")


@blp.before_request
def init_calendar_config() -> None:  # pylint: disable=missing-function-docstring
    g.inter = InterfaceApiCalendarCalendar(
        process_setting=g.process_settings,
        user_domain_settings=g.user_domain_settings,
        user=g.user,
    )


@blp.route("/calendars")
class ApiCalendarList(MethodView):
    """API to list and create calendars."""

    @blp.response(200, CalendarListResponseSchema)
    def get(self) -> ResponseReturnValue:
        """List all calendars for the current user."""
        logger_api.debug("GET /calendars user=%s", g.user.uid)
        return g.inter.get_all_calendars()

    @blp.arguments(CalendarCreateSchema)
    @blp.response(201, CalendarResponseSchema)
    def post(self, body: dict) -> ResponseReturnValue:
        """Create a new calendar."""
        logger_api.debug("POST /calendars user=%s body=%s", g.user.uid, body)
        return g.inter.create_calendar(body)


@blp.route("/calendars/<string:key>")
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


@blp.route("/calendars/<string:key>/events")
class ApiCalendarEventList(MethodView):
    """API to list and create events in a calendar."""

    @blp.arguments(CalendarEventQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarEventListResponseSchema, example=CalendarEventListResponseSchema.example())
    def get(self, query_args: dict, key: str) -> ResponseReturnValue:
        """List events in a calendar, with optional date range and search."""
        logger_api.debug("GET /calendars/%s/events args=%s", key, query_args)
        return g.inter.get_events(key, query_args)

    @blp.arguments(CalendarEventCreateSchema)
    @blp.response(201, CalendarEventResponseSchema)
    def post(self, body: dict, key: str) -> ResponseReturnValue:
        """Create a new event in the calendar."""
        logger_api.debug("POST /calendars/%s/events user=%s", key, g.user.uid)
        return g.inter.create_event(key, body)


@blp.route("/events")
class ApiEventList(MethodView):
    """API to list events across all user calendars."""

    @blp.arguments(CalendarEventQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarEventListResponseSchema)
    def get(self, query_args: dict) -> ResponseReturnValue:
        """List events across all calendars of the current user."""
        logger_api.debug("GET /events args=%s user=%s", query_args, g.user.uid)
        return g.inter.get_events(None, query_args)


@blp.route("/events/<string:event_key>")
class ApiEventDetail(MethodView):
    """API to retrieve, update and delete a single event."""

    @blp.response(200, CalendarEventResponseSchema)
    def get(self, event_key: str) -> ResponseReturnValue:
        """Get a single event by its key."""
        logger_api.debug("GET /events/%s user=%s", event_key, g.user.uid)
        return g.inter.get_event(event_key)

    @blp.arguments(CalendarEventPatchSchema)
    @blp.response(200, CalendarEventResponseSchema)
    def patch(self, body: dict, event_key: str) -> ResponseReturnValue:
        """Partially update an event."""
        logger_api.debug("PATCH /events/%s user=%s", event_key, g.user.uid)
        return g.inter.patch_event(event_key, body)

    @blp.response(200, CalendarEventResponseSchema)
    def delete(self, event_key: str) -> ResponseReturnValue:
        """Delete an event."""
        logger_api.debug("DELETE /events/%s user=%s", event_key, g.user.uid)
        return g.inter.delete_event(event_key)


@blp.route("/calendars/<string:key>/tasks")
class ApiCalendarTaskList(MethodView):
    """API to list and create tasks (VTODO) in a calendar."""

    @blp.arguments(CalendarTaskQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarTaskListResponseSchema)
    def get(self, query_args: dict, key: str) -> ResponseReturnValue:
        """List tasks in a calendar, with optional date range and search."""
        logger_api.debug("GET /calendars/%s/tasks args=%s", key, query_args)
        return g.inter.get_tasks(key, query_args)

    @blp.arguments(CalendarTaskCreateSchema)
    @blp.response(201, CalendarTaskResponseSchema)
    def post(self, body: dict, key: str) -> ResponseReturnValue:
        """Create a new task in the calendar."""
        logger_api.debug("POST /calendars/%s/tasks user=%s", key, g.user.uid)
        return g.inter.create_task(key, body)


@blp.route("/tasks")
class ApiTaskList(MethodView):
    """API to list tasks across all user calendars."""

    @blp.arguments(CalendarTaskQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarTaskListResponseSchema)
    def get(self, query_args: dict) -> ResponseReturnValue:
        """List tasks across all calendars of the current user."""
        logger_api.debug("GET /tasks args=%s user=%s", query_args, g.user.uid)
        return g.inter.get_tasks(None, query_args)


@blp.route("/tasks/<string:task_key>")
class ApiTaskDetail(MethodView):
    """API to retrieve, update and delete a single task."""

    @blp.response(200, CalendarTaskResponseSchema)
    def get(self, task_key: str) -> ResponseReturnValue:
        """Get a single task by its key."""
        logger_api.debug("GET /tasks/%s user=%s", task_key, g.user.uid)
        return g.inter.get_task(task_key)

    @blp.arguments(CalendarTaskPatchSchema)
    @blp.response(200, CalendarTaskResponseSchema)
    def patch(self, body: dict, task_key: str) -> ResponseReturnValue:
        """Partially update a task."""
        logger_api.debug("PATCH /tasks/%s user=%s", task_key, g.user.uid)
        return g.inter.patch_task(task_key, body)

    @blp.response(200, CalendarTaskResponseSchema)
    def delete(self, task_key: str) -> ResponseReturnValue:
        """Delete a task."""
        logger_api.debug("DELETE /tasks/%s user=%s", task_key, g.user.uid)
        return g.inter.delete_task(task_key)
