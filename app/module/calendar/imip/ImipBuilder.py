from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.serializer.CalEventSerializerIcal import CalEventSerializerIcal

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.CalendarUser import CalendarUser

_serializer: CalEventSerializerIcal = CalEventSerializerIcal()


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
    def build_reply(event: CalEvent, calendar_user: CalendarUser) -> ImipMessage | None:
        """Build a METHOD:REPLY on behalf of the invited party.

        The responding attendee is the calendar owner, not necessarily the connected user: on a
        delegated calendar the owner is the invitee while ``user`` is the delegate acting for them.
        Locates the attendee whose email matches the owner, then produces a REPLY VCALENDAR containing
        only that attendee (RFC 5546 §3.2.3). Returns None if the event has no organizer or the owner
        is not listed as an attendee.

        :param event: The event being responded to.
        :param calendar_user: The acting user and the calendar owner (the invitee).
        :return: The iMIP REPLY message, or None if the owner is not an attendee.
        """
        if not event.organizer:
            return None
        owner_mail: str = calendar_user.owner.mail
        # The organizer does not reply to their own event (RFC 5546): there is no one to notify.
        if event.organizer.email == owner_mail:
            return None
        replying_attendee = event.attendee_for(owner_mail)
        if replying_attendee is None:
            return None
        reply_event: CalEvent = dataclasses.replace(event, attendees=[replying_attendee])
        ical = _serializer.build_imip(reply_event, "REPLY")
        return ImipMessage(
            method=ImipMethod.REPLY,
            event=reply_event,
            from_email=owner_mail,
            to_emails=[event.organizer.email],
            ical_content=ical,
        )
