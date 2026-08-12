from __future__ import annotations  # pylint: disable=duplicate-code

from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint
from werkzeug.datastructures import FileStorage

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.api.is_async import AsyncQueryArgsSchema, async_endpoint
from app.utils.errors import ERROR_CALENDAR_IMPORT_NO_FILE
from app.utils.logger.logger import logger_api
from .schemas.calendar import (
    CalendarCreateSchema,
    CalendarUpdateSchema,
    CalendarListResponseSchema,
    CalendarResponseSchema,
    CalendarExportQueryArgsSchema,
    CalendarExportResponseSchema,
    CalendarImportResponseSchema,
    CalendarImportUploadSchema,
    CalendarSubscriptionResponseSchema,
)
from .schemas.event import (
    AttendanceSchema,
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
from .schemas.freebusy import FreeBusyRequestSchema, FreeBusyResponseSchema
from .schemas.reminder import ReminderQueryArgsSchema, ReminderListResponseSchema
from .schemas.external_calendar import (
    ExternalCalendarCreateSchema,
    ExternalCalendarUpdateSchema,
    ExternalCalendarListResponseSchema,
    ExternalCalendarResponseSchema,
    SyncStatusResponseSchema,
    SyncTriggerResponseSchema,
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
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_all_calendars()

    @blp.arguments(CalendarCreateSchema)
    @blp.response(201, CalendarResponseSchema)
    def post(self, body: dict) -> ResponseReturnValue:
        """Create a new calendar."""
        logger_api.debug("POST /calendars user=%s body=%s", g.user.uid, body)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.create_calendar(body)


@blp.route("/calendars/<string:key>")
class ApiCalendarDetail(MethodView):
    """API to retrieve, update and delete a single calendar."""

    @blp.response(200, CalendarResponseSchema)
    def get(self, key: str) -> ResponseReturnValue:
        """Get a calendar by its key."""
        logger_api.debug("GET /calendars/%s user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_calendar(key)

    @blp.arguments(CalendarUpdateSchema)
    @blp.response(200, CalendarResponseSchema)
    def patch(self, body: dict, key: str) -> ResponseReturnValue:
        """Update a calendar."""
        logger_api.debug("PATCH /calendars/%s user=%s body=%s", key, g.user.uid, body)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.update_calendar(key, body)

    @blp.response(200, CalendarResponseSchema)
    def delete(self, key: str) -> ResponseReturnValue:
        """Delete a calendar."""
        logger_api.debug("DELETE /calendars/%s user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.delete_calendar(key)


@blp.route("/calendars/<string:key>/export")
class ApiCalendarExport(MethodView):
    """Export a calendar to VCALENDAR (.ics) as an Agent job.

    The export always runs in the background: the response carries a ``job_id``
    (202). Clients poll ``GET /jobs/<job_id>`` until ``status == "success"`` then
    fetch the file with ``GET /jobs/<job_id>/result`` (add ``?download=true`` to
    trigger a browser save dialog).
    """

    @blp.arguments(CalendarExportQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(202, CalendarExportResponseSchema)
    def get(self, query_args: dict, key: str) -> ResponseReturnValue:
        """Enqueue the export and return the ``job_id`` to poll."""
        logger_api.debug("GET /calendars/%s/export user=%s args=%s", key, g.user.uid, query_args)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.export_calendar(key, query_args)


@blp.route("/calendars/<string:key>/subscription")
class ApiCalendarSubscription(MethodView):
    """API to enable or disable the public .ics subscription URL of a calendar."""

    @blp.response(200, CalendarSubscriptionResponseSchema)
    def post(self, key: str) -> ResponseReturnValue:
        """Activate the public subscription and return its URL + token."""
        logger_api.debug("POST /calendars/%s/subscription user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.enable_subscription(key)

    @blp.response(200, CalendarResponseSchema)
    def delete(self, key: str) -> ResponseReturnValue:
        """Revoke the public subscription (clears the token)."""
        logger_api.debug("DELETE /calendars/%s/subscription user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.disable_subscription(key)


@blp.route("/public/calendars/<string:token>")
class ApiCalendarPublicSubscription(MethodView):
    """Public, unauthenticated read-only access to a calendar's .ics feed.

    The token in the URL is a secret capability. ``public_access`` lets the auth middleware
    serve this route without a bearer token. Returns the full calendar as ``text/calendar``, or
    404 if the token does not match an active subscription.
    """

    public_access: bool = True

    def get(self, token: str) -> ResponseReturnValue:
        """Serve the calendar matching the token as a text/calendar feed, or 404."""
        # The token is a secret; never log it in full (capability URL - would leak access).
        logger_api.debug("GET /public/calendars/%s... (public subscription)", token[:8])
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.export_public_calendar(token)


@blp.route("/calendars/<string:key>/import")
class ApiCalendarImport(MethodView):
    """API to import a VCALENDAR (.ics) payload into a calendar.

    Per the spec, the endpoint accepts a ``multipart/form-data`` upload containing a single
    ``file`` part. The ``accepted_content_types`` class attribute tells the global
    content-type middleware to skip its default ``application/json`` rule for this route.

    By default (or with ``?is_async=true``), the import runs in the background: the response
    carries a ``job_id`` (202). Clients poll ``GET /jobs/<job_id>`` until ``status == "success"``; 
    the counters are then in the job's ``result``.

    With ``?is_async=false``, the import runs synchronously and returns the counters immediately (200).
    """

    accepted_content_types: set[str] = {"multipart/form-data"}

    @blp.arguments(CalendarImportUploadSchema, location="files")
    @blp.response(200, CalendarImportResponseSchema)
    @async_endpoint(blp)
    def post(self, files: dict, is_async:bool, key: str) -> ResponseReturnValue:
        """Import an .ics file into a calendar, optionally synchronously or asynchronously.

        By default (or with ``?is_async=true``), the import runs in the background and returns
        status 202 with a ``job_id`` for polling. With ``?is_async=false``, the import runs
        synchronously and returns status 200 with the import counters immediately.

        The total request size is already capped at the WSGI layer (MAX_CONTENT_LENGTH),
        and the module enforces the per-import size limit. The raw part is decoded to text here
        (utf-8, latin-1 fallback) - the single place the upload's charset is guessed - then handed
        to the interface as a string.

        :param files: Multipart files containing the uploaded .ics file.
        :param query_args: Query parameters including 'is_async' (defaults to true).
        :param key: Calendar key to import into.
        :return: Job ID and 202 status if async (query ?is_async=true, default),
                 or import counters and 200 status if sync (?is_async=false).
        """
        logger_api.debug("POST /calendars/%s/import user=%s is_async=%s", key, g.user.uid, is_async)
        interface: InterfaceApiCalendarCalendar = g.inter
        upload: FileStorage | None = files.get("file")
        if upload is None:
            return create_api_base_response(None, ERROR_CALENDAR_IMPORT_NO_FILE)
        raw: bytes = upload.stream.read()
        try:
            ics_text: str = raw.decode("utf-8")
        except UnicodeDecodeError:
            ics_text = raw.decode("latin-1")
        return interface.import_calendar(key, ics_text, is_async=is_async)


@blp.route("/calendars/<string:key>/events")
class ApiCalendarEventList(MethodView):
    """API to list and create events in a calendar."""

    @blp.arguments(CalendarEventQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarEventListResponseSchema, example=CalendarEventListResponseSchema.example())
    def get(self, query_args: dict, key: str) -> ResponseReturnValue:
        """List events in a calendar, with optional date range and search."""
        logger_api.debug("GET /calendars/%s/events args=%s", key, query_args)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_events(key, query_args)

    @blp.arguments(CalendarEventCreateSchema)
    @blp.response(201, CalendarEventResponseSchema)
    def post(self, body: dict, key: str) -> ResponseReturnValue:
        """Create a new event in the calendar."""
        logger_api.debug("POST /calendars/%s/events user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.create_event(key, body)


@blp.route("/events")
class ApiEventList(MethodView):
    """API to list events across all user calendars."""

    @blp.arguments(CalendarEventQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarEventListResponseSchema)
    def get(self, query_args: dict) -> ResponseReturnValue:
        """List events across all calendars of the current user."""
        logger_api.debug("GET /events args=%s user=%s", query_args, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_events(None, query_args)


@blp.route("/events/<string:event_key>")
class ApiEventDetail(MethodView):
    """API to retrieve, update and delete a single event."""

    @blp.response(200, CalendarEventResponseSchema)
    def get(self, event_key: str) -> ResponseReturnValue:
        """Get a single event by its key."""
        logger_api.debug("GET /events/%s user=%s", event_key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_event(event_key)

    @blp.arguments(CalendarEventPatchSchema)
    @blp.response(200, CalendarEventResponseSchema)
    def patch(self, body: dict, event_key: str) -> ResponseReturnValue:
        """Partially update an event."""
        logger_api.debug("PATCH /events/%s user=%s", event_key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.patch_event(event_key, body)

    @blp.response(200, CalendarEventResponseSchema)
    def delete(self, event_key: str) -> ResponseReturnValue:
        """Delete an event."""
        logger_api.debug("DELETE /events/%s user=%s", event_key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.delete_event(event_key)


@blp.route("/calendars/<string:key>/tasks")
class ApiCalendarTaskList(MethodView):
    """API to list and create tasks (VTODO) in a calendar."""

    @blp.arguments(CalendarTaskQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarTaskListResponseSchema)
    def get(self, query_args: dict, key: str) -> ResponseReturnValue:
        """List tasks in a calendar, with optional date range and search."""
        logger_api.debug("GET /calendars/%s/tasks args=%s", key, query_args)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_tasks(key, query_args)

    @blp.arguments(CalendarTaskCreateSchema)
    @blp.response(201, CalendarTaskResponseSchema)
    def post(self, body: dict, key: str) -> ResponseReturnValue:
        """Create a new task in the calendar."""
        logger_api.debug("POST /calendars/%s/tasks user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.create_task(key, body)


@blp.route("/tasks")
class ApiTaskList(MethodView):
    """API to list tasks across all user calendars."""

    @blp.arguments(CalendarTaskQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, CalendarTaskListResponseSchema)
    def get(self, query_args: dict) -> ResponseReturnValue:
        """List tasks across all calendars of the current user."""
        logger_api.debug("GET /tasks args=%s user=%s", query_args, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_tasks(None, query_args)


@blp.route("/tasks/<string:task_key>")
class ApiTaskDetail(MethodView):
    """API to retrieve, update and delete a single task."""

    @blp.response(200, CalendarTaskResponseSchema)
    def get(self, task_key: str) -> ResponseReturnValue:
        """Get a single task by its key."""
        logger_api.debug("GET /tasks/%s user=%s", task_key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_task(task_key)

    @blp.arguments(CalendarTaskPatchSchema)
    @blp.response(200, CalendarTaskResponseSchema)
    def patch(self, body: dict, task_key: str) -> ResponseReturnValue:
        """Partially update a task."""
        logger_api.debug("PATCH /tasks/%s user=%s", task_key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.patch_task(task_key, body)

    @blp.response(200, CalendarTaskResponseSchema)
    def delete(self, task_key: str) -> ResponseReturnValue:
        """Delete a task."""
        logger_api.debug("DELETE /tasks/%s user=%s", task_key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.delete_task(task_key)


@blp.route("/events/<string:event_key>/attendance")
class ApiEventAttendance(MethodView):
    """API to set the current user's attendance status for an event."""

    @blp.arguments(AttendanceSchema)
    @blp.response(200, CalendarEventResponseSchema)
    def post(self, body: dict, event_key: str) -> ResponseReturnValue:
        """Set attendance status (accepted / declined / tentative / delegated) for the current user."""
        logger_api.debug("POST /events/%s/attendance user=%s status=%s", event_key, g.user.uid, body.get("status"))
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.set_attendance_status(event_key, body)


@blp.route("/freebusy")
class ApiFreeBusy(MethodView):
    """API to query free/busy information for a user."""

    @blp.arguments(FreeBusyRequestSchema)
    @blp.response(200, FreeBusyResponseSchema)
    def post(self, body: dict) -> ResponseReturnValue:
        """Return free/busy periods for the target users as JSON."""
        logger_api.debug("POST /freebusy user=%s targets=%s", g.user.uid, body.get("target_uids"))
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_freebusy(body)


@blp.route("/reminders")
class ApiReminderList(MethodView):
    """API to list pending reminders for the current user."""

    @blp.arguments(ReminderQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, ReminderListResponseSchema)
    def get(self, query_args: dict) -> ResponseReturnValue:
        """Return reminders whose trigger_at falls within the next N minutes."""
        logger_api.debug("GET /reminders user=%s args=%s", g.user.uid, query_args)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_reminders(query_args)


@blp.route("/external-calendars")
class ApiExternalCalendarList(MethodView):
    """API to list and create external ICS calendar subscriptions."""

    @blp.response(200, ExternalCalendarListResponseSchema)
    def get(self) -> ResponseReturnValue:
        """List all external calendar subscriptions for the current user."""
        logger_api.debug("GET /external-calendars user=%s", g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_all_calendars(source_type="ics")

    @blp.arguments(ExternalCalendarCreateSchema)
    @blp.response(201, ExternalCalendarResponseSchema)
    def post(self, body: dict) -> ResponseReturnValue:
        """Create a new external ICS calendar subscription."""
        logger_api.debug("POST /external-calendars user=%s url=%s", g.user.uid, body.get("url"))
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.create_external_calendar(body)


@blp.route("/external-calendars/<string:key>")
class ApiExternalCalendarDetail(MethodView):
    """API to retrieve, update and delete an external ICS calendar."""

    @blp.response(200, ExternalCalendarResponseSchema)
    def get(self, key: str) -> ResponseReturnValue:
        """Get an external calendar by its key."""
        logger_api.debug("GET /external-calendars/%s user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_calendar(key)

    @blp.arguments(ExternalCalendarUpdateSchema)
    @blp.response(200, ExternalCalendarResponseSchema)
    def put(self, body: dict, key: str) -> ResponseReturnValue:
        """Update an external calendar."""
        logger_api.debug("PUT /external-calendars/%s user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.update_calendar(key, body)

    @blp.response(200, ExternalCalendarResponseSchema)
    def delete(self, key: str) -> ResponseReturnValue:
        """Delete an external calendar and all its mirrored events."""
        logger_api.debug("DELETE /external-calendars/%s user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.delete_calendar(key)


@blp.route("/external-calendars/<string:key>/sync")
class ApiExternalCalendarSync(MethodView):
    """API to trigger and monitor sync for an external ICS calendar."""

    @blp.response(200, SyncStatusResponseSchema)
    def get(self, key: str) -> ResponseReturnValue:
        """Get the sync status for an external calendar."""
        logger_api.debug("GET /external-calendars/%s/sync user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.get_sync_status(key)

    @blp.response(202, SyncTriggerResponseSchema)
    def post(self, key: str) -> ResponseReturnValue:
        """Enqueue a manual sync for an external calendar (returns a job_id)."""
        logger_api.debug("POST /external-calendars/%s/sync user=%s", key, g.user.uid)
        interface: InterfaceApiCalendarCalendar = g.inter
        return interface.sync_external_calendar(key)
