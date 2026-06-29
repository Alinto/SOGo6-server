from __future__ import annotations

import email as email_lib
from email.message import Message
from email.utils import getaddresses, parseaddr
from typing import TYPE_CHECKING, cast

from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.serializer.CalEventDeserializerIcal import CalEventDeserializerIcal
from app.module.calendar.serializer.EnvelopeIcal import EnvelopeIcal
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

_deserializer: CalEventDeserializerIcal = CalEventDeserializerIcal()


class ImipParser:
    """Parses raw email bytes containing an iMIP payload into an ImipMessage.

    Intended for use by the asynchronous agent when polling incoming mail.
    Uses only stdlib (email, re) for MIME parsing; delegates iCalendar
    parsing to CalEventDeserializerIcal.
    """

    @staticmethod
    def parse(raw_bytes: bytes) -> ImipMessage:
        """Parse a raw iMIP email and return an ImipMessage.

        :param raw_bytes: Raw email bytes as fetched from IMAP.
        :type raw_bytes: bytes
        :return: Parsed message with method, event, sender and recipient addresses.
        :rtype: ImipMessage
        :raises RequestException: If no text/calendar part is found or the METHOD is missing/unsupported.
        """
        msg: Message = email_lib.message_from_bytes(raw_bytes)
        _, from_email = parseaddr(msg.get("From", ""))
        to_emails: list[str] = [
            addr for _, addr in getaddresses(msg.get_all("To", []))
            if addr
        ]

        ical_content = ImipParser._extract_ical(msg)
        if not ical_content:
            raise RequestException(error=err.ERROR_CALENDAR_ICS_PARSE_FAILED)

        method = ImipParser._extract_method(ical_content)
        event = _deserializer.deserialize(ical_content)

        return ImipMessage(
            method=method,
            event=event,
            from_email=from_email,
            to_emails=to_emails,
            ical_content=ical_content,
        )

    @staticmethod
    def parse_calendar(ical_bytes: bytes, from_email: str = "") -> ImipMessage:
        """Parse a raw text/calendar payload (no MIME envelope) into an ImipMessage.

        Counterpart of :meth:`parse` for callers that already hold the calendar object itself - e.g.
        the mail interface, which gets the extracted text/calendar part from an opened mail. The
        sender is not part of the payload, so it is supplied separately (empty by default).

        :param ical_bytes: Raw iCalendar (VCALENDAR) bytes.
        :param from_email: Sender address, when known by the caller.
        :return: The parsed message (method, event, sender, ical_content); to_emails stays empty.
        :raises RequestException: If the METHOD is missing/unsupported or the iCalendar cannot be read.
        """
        ical_content: str = ical_bytes.decode("utf-8", errors="replace")
        method: ImipMethod = ImipParser._extract_method(ical_content)
        event: CalEvent = _deserializer.deserialize(ical_content)
        return ImipMessage(
            method=method,
            event=event,
            from_email=from_email,
            to_emails=[],
            ical_content=ical_content,
        )

    @staticmethod
    def _extract_ical(msg: Message) -> str | None:
        """Walk MIME parts and return the first text/calendar payload as a string."""
        for part in msg.walk():
            if part.get_content_type() == "text/calendar":
                payload: bytes | None = cast("bytes | None", part.get_payload(decode=True))
                if payload:
                    charset: str = part.get_content_charset("utf-8")
                    return payload.decode(charset)
        return None

    @staticmethod
    def detect_method(ical_bytes: bytes) -> ImipMethod | None:
        """Return the scheduling iTIP METHOD declared in an iCalendar payload, or None.

        Non-raising: yields None when the payload carries no METHOD property (a plain calendar
        export) or declares a method we do not route (e.g. PUBLISH, COUNTER). Used to recognise
        an iMIP attachment and its kind before committing to full processing.

        :param ical_bytes: Raw text/calendar attachment bytes.
        :return: The detected method, or None when absent or unsupported.
        """
        text: str = ical_bytes.decode("utf-8", errors="replace")
        method: str | None = EnvelopeIcal.read_method(text)
        if method is None:
            return None
        try:
            return ImipMethod(method)
        except ValueError:
            return None

    @staticmethod
    def _extract_method(ical_content: str) -> ImipMethod:
        """Extract and validate the METHOD property from a VCALENDAR string."""
        method: ImipMethod | None = ImipParser.detect_method(ical_content.encode("utf-8"))
        if method is None:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_INVALID_REQUEST)
        return method
