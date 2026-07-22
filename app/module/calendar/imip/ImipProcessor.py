from __future__ import annotations

# pylint: disable=raise-missing-from
import dataclasses
from typing import TYPE_CHECKING

from app.module.calendar.attendance.AttendanceProcessor import AttendanceProcessor
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.imip.ImipParser import ImipParser
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.auth.User import User
    from app.module.calendar.model.CalAttendee import CalAttendee
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
        """Parse a raw text/calendar payload and validate its METHOD.

        The bytes are the iCalendar object itself, not a full MIME email: unwrapping the email is the
        caller's job (the agent uses ImipParser.parse on the raw mail; the mail interface already holds
        the extracted text/calendar part). The sender address is supplied separately by the caller.

        :raises RequestException: ERROR_CALENDAR_ICS_PARSE_FAILED on parse failure.
        :raises RequestException: ERROR_CALENDAR_IMIP_INVALID_REQUEST if the METHOD does not match.
        """
        try:
            message: ImipMessage = ImipParser.parse_calendar(ical_bytes)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Failed to parse iMIP iCalendar payload")
            raise RequestException(error=err.ERROR_CALENDAR_ICS_PARSE_FAILED) from exc
        if message.method != expected_method:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_INVALID_REQUEST)
        return message

    @staticmethod
    def _require_sender_is_organizer(event: CalEvent, from_email: str) -> None:
        """Reject an iMIP REQUEST/CANCEL whose sender is not the event's organizer.

        Only the organizer may create, update or cancel an event for an attendee (RFC 5546 §3.2 /
        RFC 6047 security considerations). For an existing event the LOCAL organizer is checked - the
        incoming message's organizer is attacker-controlled - so a forged mail opened by the victim
        cannot overwrite or delete their event by reusing its UID.
        """
        if not event.is_organized_by(from_email):
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_SENDER_MISMATCH)

    def process_reply(self, owner: User, ical_bytes: bytes, from_email: str) -> CalEvent | None:
        """Process an incoming iMIP REPLY by updating the attendee status on the local event.

        Validates that the message reached the organizer's copy and that the sender is the attendee
        it answers for, then hands the response to AttendanceProcessor, which resolves the targeted
        occurrence, refuses obsolete revisions and mirrors the status to the local copies.
        Does not increment SEQUENCE - a REPLY does not alter event content (RFC 5545 §3.8.7.4).

        The From: header is taken on trust: nothing here proves the sender is who they claim. On this
        path the caller only holds the extracted text/calendar part, so no DKIM signature is available
        to check. Spoofing protection is therefore delegated to the MTA (SPF/DKIM/DMARC) upstream.

        :param owner: The calendar owner receiving the reply (the organizer).
        :param ical_bytes: Raw iCalendar bytes from the iMIP email body.
        :param from_email: Email of the replying attendee (From: header of the iMIP message).
        :return: The updated event, or None when the reply is not ours to apply - unknown event,
            not addressed to the organizer, obsolete revision, sender absent from the targeted row,
            or a slot the organizer cancelled.
        """
        message: ImipMessage = self._parse_and_validate(ical_bytes, ImipMethod.REPLY)

        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(owner.uid, message.event.require_uid)
        if result is None:
            logger_calendar.info(
                "iMIP REPLY for unknown event uid=%s from=%s - ignored", message.event.uid, from_email
            )
            return None

        source, event = result
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

        # Attendee responses are recorded on the organizer's copy only. A REPLY landing in another
        # attendee's mailbox is misdirected, not hostile - drop it without raising. Logged as a
        # warning rather than an error: it is anomalous, but caused by an external sender and there
        # is nothing an operator can act on.
        if not event.is_organized_by(owner.mail):
            logger_calendar.warning(
                "iMIP REPLY for uid=%s received by %s who is not the organizer - ignored",
                message.event.uid, owner.mail,
            )
            return None

        # Who is answering is decided from the stored guest list, never from the payload. Matching
        # SENT-BY (RFC 5545 §3.2.18) against the incoming attendee would be circular: a forged reply
        # would simply name its own delegate. Read from our copy, the delegation had to be recorded
        # by a path the organizer controls, which is what RFC 6047 §3 asks for.
        #
        # SECURITY: this still binds the response to an unverified identity. from_email comes from
        # the From: header and nothing here authenticates it, so anyone able to forge that header can
        # flip the PARTSTAT of an existing attendee on an event whose UID they know - and UIDs leak
        # through every ICS export, subscription feed and invitation. The deployment MUST reject
        # spoofed senders at the MTA; that is the only thing standing between this and impersonation.
        # The guest list that arbitrates is the one of the row the reply targets: an attendee may
        # have been invited to a single occurrence only, in which case the master never lists them.
        guest_list: CalEvent = event
        if message.event.recurrence_id is not None:
            occurrence: CalEvent | None = source.get_event_by_recurrence_id(
                event.require_uid, message.event.recurrence_id,
            )
            if occurrence is not None:
                guest_list = occurrence
        answering: list[CalAttendee] = [
            att for att in guest_list.attendees if from_email in (att.email, att.sent_by)
        ]
        if len(answering) != 1:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_REPLY_SENDER_MISMATCH)

        # RFC 5546 §3.2.3 constrains a REPLY to one ATTENDEE, but clients routinely echo the
        # organizer or the whole guest list, so only the sender's own answer is read out of it.
        replier: CalAttendee | None = next(
            (att for att in message.event.attendees if att.email == answering[0].email), None
        )
        if replier is None:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_REPLY_SENDER_MISMATCH)

        # TODO: handle delegation. RFC 5546 §3.2.2.3 has the delegator reply PARTSTAT=DELEGATED with
        # DELEGATED-TO plus a new ATTENDEE for the delegate; only the PARTSTAT is applied here, so the
        # delegate is never added to the stored guest list and the reply they must send in turn finds
        # no match. Deserialization already carries delegated_to, and storing it is also what would
        # let a delegate's SENT-BY be recognised on the next reply.
        try:
            return AttendanceProcessor.apply_response(
                source=source,
                event=event,
                attendee_email=replier.email,
                status=replier.status,
                recurrence_id=message.event.recurrence_id,
                # An omitted SEQUENCE reaches us as 0, which is what RFC 5545 §3.8.7.4 says it
                # means: the reply answers revision 0. Against a stored revision it is stale like
                # any other, and refusing it is what keeps the guard from being sidestepped by
                # simply leaving the property out.
                incoming_sequence=message.event.sequence,
            )
        except RequestException as exc:
            # Not ours to apply - the sender is absent from the row actually targeted, or the slot
            # was cancelled by the organizer. Same drop-without-raising policy as the checks above.
            if exc.error in (err.ERROR_CALENDAR_NOT_ATTENDEE, err.ERROR_CALENDAR_OCCURRENCE_NOT_FOUND):
                logger_calendar.warning(
                    "iMIP REPLY for uid=%s from %s refused (%s) - ignored",
                    message.event.uid, from_email, exc.error.c,
                )
                return None
            raise
        except Exception as exc:
            logger_calendar.exception(
                "Unexpected error applying iMIP reply for event uid=%s", message.event.uid,
            )
            raise RequestException(error=err.ERROR_CALENDAR_ATTENDANCE_UPDATE_FAILED) from exc

    def process_request(self, owner: User, ical_bytes: bytes, from_email: str) -> CalEvent:
        """Process an incoming iMIP REQUEST, adding or updating the event in the owner's calendar.

        When the event already exists (matched by UID), its mutable content fields are updated.
        When it does not exist, it is inserted into the owner's default calendar.
        Called when an attendee's mailbox receives an invitation or update.

        :param owner: The attendee (calendar owner) receiving the invitation.
        :param ical_bytes: Raw iCalendar bytes from the iMIP email body.
        :param from_email: Sender (From: header); must match the event organizer or the message is rejected.
        :return: The created or updated event.
        """
        message: ImipMessage = self._parse_and_validate(ical_bytes, ImipMethod.REQUEST)
        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(owner.uid, message.event.require_uid)

        if result is not None:
            source, existing = result
            if not source.is_writable():
                raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
            # Only the existing event's organizer may update it (the incoming organizer is untrusted).
            self._require_sender_is_organizer(existing, from_email)
            # A REQUEST carrying RECURRENCE-ID updates one instance: it must land on the detached
            # occurrence, never on the master - its component has no RRULE and single-instance
            # dates, so applying it to the master would collapse the whole series.
            target: CalEvent = existing
            if message.event.recurrence_id is not None:
                occurrence: CalEvent | None = source.get_event_by_recurrence_id(
                    existing.require_uid, message.event.recurrence_id,
                )
                if occurrence is not None:
                    target = occurrence
            # Reject stale updates (RFC 5546 §3.2.2): ignore if the incoming SEQUENCE is lower
            if not target.accepts_revision(message.event.sequence):
                logger_calendar.info(
                    "Stale iMIP REQUEST for uid=%s (local seq=%d > incoming seq=%d) - ignored",
                    message.event.uid, target.sequence, message.event.sequence,
                )
                return target
            if message.event.recurrence_id is not None and target is existing:
                target = source.get_or_create_occurrence(existing, message.event.recurrence_id)
            # Apply shared content only: each user keeps their own reminders and conference data
            target.apply_organizer_content(message.event)
            return source.update_event_or_fail(target, "processing iMIP request")

        # New invitation: the sender must be the organizer it claims in the payload.
        self._require_sender_is_organizer(message.event, from_email)
        # Event not in the owner's calendars - insert into the default calendar
        default_source: CalendarSource | None = self._sources.get_default(owner.uid)
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

    def process_cancel(self, owner: User, ical_bytes: bytes, from_email: str) -> None:
        """Process an incoming iMIP CANCEL, removing the event from the owner's calendar.

        For a full cancellation (no RECURRENCE-ID), soft-deletes the event series.
        For a partial cancellation (RECURRENCE-ID present), adds the date to EXDATE on the
        master event rather than looking for a detached occurrence row that may not exist.
        Silently ignores CANCELs for events not found in the owner's calendars.

        :param owner: The attendee (calendar owner) receiving the cancellation.
        :param ical_bytes: Raw iCalendar bytes from the iMIP email body.
        :param from_email: Sender (From: header); must match the event organizer or the message is rejected.
        """
        message: ImipMessage = self._parse_and_validate(ical_bytes, ImipMethod.CANCEL)
        result: tuple[CalendarSource, CalEvent] | None = self._sources.find_by_uid(owner.uid, message.event.require_uid)

        if result is None:
            logger_calendar.info(
                "iMIP CANCEL for unknown event uid=%s from=%s - ignored", message.event.uid, from_email
            )
            return

        source, master = result
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        # Only the existing event's organizer may cancel it (the incoming organizer is untrusted).
        self._require_sender_is_organizer(master, from_email)

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
