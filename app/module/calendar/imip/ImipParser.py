from __future__ import annotations

import email as email_lib
import re
from email.message import Message

from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.utils import errors as err
from app.utils.exceptions import RequestException

_deserializer: CalendarEventDeserializerIcal = CalendarEventDeserializerIcal()


class ImipParser:
    """Parses raw email bytes containing an iMIP payload into an ImipMessage.

    Intended for use by the asynchronous agent when polling incoming mail.
    Uses only stdlib (email, re) for MIME parsing; delegates iCalendar
    parsing to CalendarEventDeserializerIcal.
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
        _, from_email = email_lib.utils.parseaddr(msg.get("From", ""))
        to_emails: list[str] = [
            addr for _, addr in email_lib.utils.getaddresses(msg.get_all("To", []))
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
    def _extract_ical(msg: Message) -> str | None:
        """Walk MIME parts and return the first text/calendar payload as a string."""
        for part in msg.walk():
            if part.get_content_type() == "text/calendar":
                payload: bytes | None = part.get_payload(decode=True)
                if payload:
                    charset: str = part.get_content_charset("utf-8")
                    return payload.decode(charset)
        return None

    @staticmethod
    def _extract_method(ical_content: str) -> ImipMethod:
        """Extract and validate the METHOD property from a VCALENDAR string."""
        match = re.search(r'^METHOD:([A-Z]+)', ical_content, re.MULTILINE)
        if not match:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_INVALID_REQUEST)
        try:
            return ImipMethod(match.group(1))
        except ValueError as exc:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_INVALID_REQUEST) from exc
