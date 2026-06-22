"""Turns an ImipMessage into the RFC 6047 email that carries it (text/calendar; method=...)."""
from __future__ import annotations

from email.message import EmailMessage
from typing import TYPE_CHECKING

from app.module.calendar.CalendarConst import (
    IMIP_SUBJECT_PREFIX_CANCEL,
    IMIP_SUBJECT_PREFIX_REPLY,
    IMIP_SUBJECT_PREFIX_REQUEST,
)
from app.module.calendar.imip.ImipMethod import ImipMethod

if TYPE_CHECKING:
    from app.module.calendar.imip.ImipMessage import ImipMessage

# Subject prefix per method - the human-facing hint, the machine part is the text/calendar body.
_SUBJECT_PREFIX: dict[ImipMethod, str] = {
    ImipMethod.REQUEST: IMIP_SUBJECT_PREFIX_REQUEST,
    ImipMethod.REPLY: IMIP_SUBJECT_PREFIX_REPLY,
    ImipMethod.CANCEL: IMIP_SUBJECT_PREFIX_CANCEL,
}


class ImipEmailBuilder:
    """Builds the outgoing email (multipart/alternative: text/plain + text/calendar) for an iMIP message."""

    @staticmethod
    def build_email(message: ImipMessage) -> EmailMessage:
        """Wrap an ImipMessage in an RFC 6047 email ready for the outgoing mail client.

        The body is the iCalendar object itself (``text/calendar`` carrying the iTIP ``method`` and
        ``component`` parameters); calendar-aware clients render the invitation from it. No text/plain
        alternative is added - it would only be a fixed, untranslated courtesy line that capable
        clients ignore anyway.

        :param message: the iMIP message to deliver (method, ical_content, from/to).
        :return: the email to hand to ``ClientOutgoing.send_mail``.
        """
        email_message: EmailMessage = EmailMessage()
        email_message["From"] = message.from_email
        email_message["To"] = ", ".join(message.to_emails)
        title: str = message.event.title or message.event.uid or "Untitled"
        email_message["Subject"] = f"{_SUBJECT_PREFIX[message.method]}: {title}"
        email_message.set_content(
            message.ical_content, subtype="calendar",
            params={"method": message.method.value, "component": "VEVENT"},
        )
        return email_message
