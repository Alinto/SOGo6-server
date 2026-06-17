from __future__ import annotations

import email as email_lib
import re
from email.message import Message
from email.utils import getaddresses, parseaddr
from typing import cast

from app.module.calendar.imip.ImipMessage import ImipMessage
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.serializer.CalEventDeserializerIcal import CalEventDeserializerIcal
from app.utils import errors as err
from app.utils.exceptions import RequestException

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
        match = re.search(r'^METHOD:([A-Z]+)', text, re.MULTILINE)
        if not match:
            return None
        try:
            return ImipMethod(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_method(ical_content: str) -> ImipMethod:
        """Extract and validate the METHOD property from a VCALENDAR string."""
        method: ImipMethod | None = ImipParser.detect_method(ical_content.encode("utf-8"))
        if method is None:
            raise RequestException(error=err.ERROR_CALENDAR_IMIP_INVALID_REQUEST)
        return method
