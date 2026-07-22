from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from datetime import datetime

    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
    from app.module.calendar.source.CalendarSource import CalendarSource


class AttendanceProcessor:
    """Applies an attendee participation status on a stored event.

    Shared by every path through which a response can reach a calendar - a user answering their own
    invitation, or an inbound iMIP REPLY - so they resolve the target occurrence, arbitrate the
    revision and propagate identically. Callers keep what is specific to them: permission checks
    for a direct answer, organizer and sender validation for iMIP.
    """

    @staticmethod
    def apply_response(
        source: CalendarSource,
        event: CalEvent,
        attendee_email: str,
        status: AttendeeStatus,
        incoming_sequence: int,
        recurrence_id: datetime | None = None,
    ) -> CalEvent | None:
        """Set attendee_email's PARTSTAT on the targeted event and mirror it to the local copies.

        Writes nothing when the status is already current: PARTSTAT is the only field touched here,
        so a no-op write would move the ETag and trigger a pointless resynchronization on every
        CalDAV client. A refused response leaves no trace at all - in particular it never detaches
        the occurrence it targeted.

        :param source: Source holding the event, used for the occurrence lookup and the writes.
        :param event: Master event of the series, or the standalone event.
        :param attendee_email: Address of the attendee whose status is being set.
        :param status: The participation status to apply.
        :param incoming_sequence: Revision the response answers. A strictly older one is refused.
            Always known: a direct answer carries the revision the user was shown, and an iMIP
            message omitting SEQUENCE is answering revision 0 by RFC 5545 §3.8.7.4.
        :param recurrence_id: When set, target that single occurrence, detaching it if needed.
        :return: The targeted event, or None when the response was refused as an obsolete revision.
        :raises RequestException: ERROR_CALENDAR_NOT_ATTENDEE when attendee_email is absent from the
            event - answering for an event one was not invited to is reported, never silently kept.
        :raises RequestException: ERROR_CALENDAR_OCCURRENCE_NOT_FOUND when recurrence_id names a
            slot the organizer cancelled.
        """
        # Detaching writes a row and adds an EXDATE on the master, so every gate below runs first: a
        # response that ends up refused must leave the stored series untouched. Until the occurrence
        # exists, the master carries the revision and the attendee list it would inherit, so it is
        # what the gates read.
        target: CalEvent = event
        if recurrence_id is not None:
            existing: CalEvent | None = source.get_event_by_recurrence_id(event.require_uid, recurrence_id)
            if existing is not None:
                target = existing
            elif recurrence_id in (event.recurrence_exceptions or []):
                # An EXDATE with no live override row means the organizer cancelled that single
                # slot. Materializing an occurrence for it would resurrect the cancelled instance,
                # since overrides take precedence over EXDATE in expansion.
                raise RequestException(error=err.ERROR_CALENDAR_OCCURRENCE_NOT_FOUND)

        if not target.accepts_revision(incoming_sequence):
            logger_calendar.info(
                "Obsolete attendance response for uid=%s attendee=%s (local seq=%d > incoming seq=%d) - ignored",
                target.uid, attendee_email, target.sequence, incoming_sequence,
            )
            return None

        if target.attendance_status_for(attendee_email) == status:
            return target

        if attendee_email not in [a.email for a in target.attendees]:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_ATTENDEE)

        if recurrence_id is not None and target is event:
            target = source.get_or_create_occurrence(event, recurrence_id)

        target.set_attendance(attendee_email, status)
        source.update_event_or_fail(target, "applying an attendance response")
        source.propagate_partstat_to_copies(event=target, attendee_email=attendee_email, status=status)
        return target
