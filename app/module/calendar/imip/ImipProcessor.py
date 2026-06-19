from __future__ import annotations

# pylint: disable=raise-missing-from
import dataclasses
from typing import TYPE_CHECKING

from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.imip.ImipParser import ImipParser
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

from app.module.calendar.model.CalAttendee import CalAttendee

if TYPE_CHECKING:
    from app.auth.User import User
    from app.module.calendar.imip.ImipMessage import ImipMessage
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.source.CalendarSource import CalendarSource
    from app.module.calendar.source.CalendarSources import CalendarSources


class ImipProcessor:
    """Processes incoming iMIP messages (RFC 6047) on behalf of a calendar user.

    Delegates cross-user lookups to CalendarSources and write operations to the
    CalendarSource returned by those lookups. Designed to be called by:
    - The Celery agent when it detects an iMIP email in the user's mailbox.
    - ModuleCalendar thin-wrapper methods for backward compatibility.
    """

    def __init__(self, sources: CalendarSources) -> None:
        self._sources = sources

    @staticmethod
    def _parse_and_validate(ical_bytes: bytes, expected_method: ImipMethod) -> ImipMessage:
        """Parse raw iCal bytes and validate the METHOD field.

        :raises RequestException: ERROR_CALENDAR_ICS_PARSE_FAILED on parse failure.
        :raises RequestException: ERROR_CALENDAR_IMIP_INVALID_REQUEST if the METHOD does not match.
        """
        try:
            message: ImipMessage = ImipParser.parse(ical_bytes)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Failed to parse iMIP bytes")
            raise RequestException(error=err.ERROR_CALENDAR_ICS_PARSE_FAILED) from exc
        if message.method != expected_method:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_INVALID_REQUEST)
        return message

    def _find_writable_source_by_uid(self, user: User, uid: str) -> tuple[CalendarSource, CalEvent]:
        """Return the source and master event for uid in user's calendars, ensuring writability.

        :raises RequestException: ERROR_CALENDAR_EVENT_NOT_FOUND if no matching event exists.
        :raises RequestException: ERROR_CALENDAR_NOT_SUPPORTED if the source is read-only.
        """
        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(user.uid, uid)
        if result is None:
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
        source, event = result
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        return source, event

    def process_reply(self, user: User, ical_bytes: bytes, from_email: str) -> CalEvent:
        """Process an incoming iMIP REPLY by updating the attendee status on the local event.

        Parses the raw iCal bytes, finds the event by UID in the user's calendars (the organizer),
        locates the attendee matching from_email, updates their PARTSTAT, and persists.
        Does not increment SEQUENCE - a REPLY does not alter event content (RFC 5545 §3.8.7.4).

        :param user: The calendar owner receiving the reply (the organizer).
        :param ical_bytes: Raw iCalendar bytes from the iMIP email body.
        :param from_email: Email of the replying attendee (From: header of the iMIP message).
        :return: The updated event.
        """
        message: ImipMessage = self._parse_and_validate(ical_bytes, ImipMethod.REPLY)
        source, event = self._find_writable_source_by_uid(user, message.event.require_uid)

        reply_by_email: dict[str, CalAttendee] = {a.email: a for a in message.event.attendees}
        for attendee in event.attendees:
            if attendee.email == from_email and attendee.email in reply_by_email:
                attendee.status = reply_by_email[attendee.email].status
                break

        try:
            source.update_event(event)
            return event
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error processing iMIP reply for event %s", message.event.uid)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

    def process_request(self, user: User, ical_bytes: bytes, from_email: str) -> CalEvent:
        """Process an incoming iMIP REQUEST, adding or updating the event in the user's calendar.

        When the event already exists (matched by UID), its mutable content fields are updated.
        When it does not exist, it is inserted into the user's default calendar.
        Called when an attendee's mailbox receives an invitation or update.

        :param user: The attendee receiving the invitation.
        :param ical_bytes: Raw iCalendar bytes from the iMIP email body.
        :param from_email: Email of the organizer (From: header, for logging).
        :return: The created or updated event.
        """
        message: ImipMessage = self._parse_and_validate(ical_bytes, ImipMethod.REQUEST)
        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(user.uid, message.event.require_uid)

        if result is not None:
            source, existing = result
            if not source.is_writable():
                raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
            # Reject stale updates (RFC 5546 §3.2.2): ignore if the incoming SEQUENCE is lower
            if message.event.sequence < existing.sequence:
                logger_calendar.info(
                    "Stale iMIP REQUEST for uid=%s (local seq=%d > incoming seq=%d) - ignored",
                    message.event.uid, existing.sequence, message.event.sequence,
                )
                return existing
            # Exclude attendee-personal fields: each user keeps their own reminders and conference data
            content_fields: frozenset[str] = message.event.MUTABLE_FIELDS - frozenset({"reminders", "conference_data"})
            existing.apply_update({f: getattr(message.event, f) for f in content_fields})
            try:
                source.update_event(existing)
                return existing
            except RequestException:
                raise
            except Exception as exc:
                logger_calendar.exception(
                    "Unexpected error updating iMIP REQUEST event uid=%s", message.event.uid,
                )
                raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

        # Event not in user's calendars - insert into the default calendar
        default_source: CalendarSource | None = self._sources.get_default(user.uid)
        if default_source is None:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
        try:
            # Strip personal fields before inserting the organizer's copy
            attendee_event: CalEvent = dataclasses.replace(message.event, reminders=[])
            return default_source.insert_event(attendee_event)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception(
                "Unexpected error inserting iMIP REQUEST event uid=%s from=%s",
                message.event.uid, from_email,
            )
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED) from exc

    def process_cancel(self, user: User, ical_bytes: bytes, from_email: str) -> None:
        """Process an incoming iMIP CANCEL, removing the event from the user's calendar.

        For a full cancellation (no RECURRENCE-ID), soft-deletes the event series.
        For a partial cancellation (RECURRENCE-ID present), adds the date to EXDATE on the
        master event rather than looking for a detached occurrence row that may not exist.
        Silently ignores CANCELs for events not found in the user's calendars.

        :param user: The attendee receiving the cancellation.
        :param ical_bytes: Raw iCalendar bytes from the iMIP email body.
        :param from_email: Email of the organizer (From: header, for logging).
        """
        message: ImipMessage = self._parse_and_validate(ical_bytes, ImipMethod.CANCEL)
        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(user.uid, message.event.require_uid)

        if result is None:
            logger_calendar.info(
                "iMIP CANCEL for unknown event uid=%s from=%s - ignored", message.event.uid, from_email
            )
            return

        source, master = result
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

        try:
            if message.event.recurrence_id is not None:
                # Partial cancel: mark the slot as an exception on the master RRULE
                if message.event.recurrence_id not in (master.recurrence_exceptions or []):
                    master.recurrence_exceptions = list(master.recurrence_exceptions or []) + [message.event.recurrence_id]
                    source.update_event(master)
            else:
                source.delete_event(master.require_uid)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception(
                "Unexpected error processing iMIP cancel for event uid=%s", message.event.uid,
            )
            raise RequestException(error=err.ERROR_UNKOWN) from exc
