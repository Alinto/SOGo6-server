from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal

if TYPE_CHECKING:
    from app.auth.User import User
    from app.module.calendar.model.CalEvent import CalEvent

_serializer: CalendarEventSerializerIcal = CalendarEventSerializerIcal()


class ImipBuilder:
    """Builds outgoing iMIP email payloads from CalEvent objects (RFC 6047)."""

    @staticmethod
    def build_request(event: CalEvent) -> ImipMessage | None:
        """Build a METHOD:REQUEST message addressed to all attendees.

        Sent when an organizer creates or updates an event with attendees.
        Returns None if the event has no organizer or no attendees.
        """
        if not event.organizer or not event.attendees:
            return None
        ical = _serializer.build_imip(event, "REQUEST")
        return ImipMessage(
            method=ImipMethod.REQUEST,
            event=event,
            from_email=event.organizer.email,
            to_emails=[a.email for a in event.attendees],
            ical_content=ical,
        )

    @staticmethod
    def build_cancel(event: CalEvent) -> ImipMessage | None:
        """Build a METHOD:CANCEL message addressed to all attendees.

        Sent when an organizer deletes an event that has attendees.
        Returns None if the event has no organizer or no attendees.
        """
        if not event.organizer or not event.attendees:
            return None
        ical = _serializer.build_imip(event, "CANCEL")
        return ImipMessage(
            method=ImipMethod.CANCEL,
            event=event,
            from_email=event.organizer.email,
            to_emails=[a.email for a in event.attendees],
            ical_content=ical,
        )

    @staticmethod
    def build_reply(event: CalEvent, user: User) -> ImipMessage | None:
        """Build a METHOD:REPLY on behalf of the attending user.

        Locates the attendee whose email matches user.uid, then produces a REPLY
        VCALENDAR containing only that attendee (RFC 5546 §3.2.3).
        Returns None if the event has no organizer or the user is not listed as an attendee.

        :param event: The event the user is responding to.
        :type event: CalEvent
        :param user: The attendee who is replying.
        :type user: User
        :return: The iMIP REPLY message, or None if the user is not an attendee.
        :rtype: ImipMessage | None
        """
        if not event.organizer:
            return None
        replying_attendee = next(
            (a for a in event.attendees if a.email == user.uid),
            None,
        )
        if replying_attendee is None:
            return None
        reply_event: CalEvent = dataclasses.replace(event, attendees=[replying_attendee])
        ical = _serializer.build_imip(reply_event, "REPLY")
        return ImipMessage(
            method=ImipMethod.REPLY,
            event=reply_event,
            from_email=user.uid,
            to_emails=[event.organizer.email],
            ical_content=ical,
        )
