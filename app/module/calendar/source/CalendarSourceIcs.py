# pylint: disable=wrong-import-order,ungrouped-imports
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from typing import TYPE_CHECKING

from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils.errors import ERROR_CALENDAR_ICS_FETCH_FAILED
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal

_MAX_ICS_BYTES = 10 * 1024 * 1024  # 10 MB
_FETCH_TIMEOUT_SECONDS = 10


class CalendarSourceIcs(CalendarSource):
    """CalendarSource backed by a remote ICS URL.

    Fetches the full ICS feed on each call. Date filtering, RRULE expansion
    and search are handled by the base class.
    """

    def __init__(self, calendar: CalCalendar, ics_url: str, deserializer: CalendarEventsDeserializerIcal) -> None:
        super().__init__(calendar)
        self._validate_url(ics_url)
        self._ics_url: str = ics_url
        self._deserializer: CalendarEventsDeserializerIcal = deserializer

    def _fetch_events(self, start: datetime, end: datetime) -> list[CalEvent]:
        ics_text: str = self._fetch_ics()
        events: list[CalEvent] = self._deserializer.deserialize(ics_text)
        logger_calendar.debug("ICS feed returned %d raw events", len(events))
        return events

    def _fetch_ics(self) -> str:
        """Download ICS content from the configured URL."""
        logger_calendar.debug("Fetching ICS from %s", self._ics_url)
        try:
            with urllib.request.urlopen(self._ics_url, timeout=_FETCH_TIMEOUT_SECONDS) as response:
                raw: bytes = response.read(_MAX_ICS_BYTES + 1)
                if len(raw) > _MAX_ICS_BYTES:
                    logger_calendar.error("ICS feed from %s exceeds size limit (%d bytes)", self._ics_url, _MAX_ICS_BYTES)
                    raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("latin-1")
        except RequestException:
            raise
        except urllib.error.HTTPError as exc:
            logger_calendar.error("HTTP %s fetching ICS from %s: %s", exc.code, self._ics_url, self._sanitize(exc.reason))
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc
        except urllib.error.URLError as exc:
            logger_calendar.error("Failed to fetch ICS from %s: %s", self._ics_url, self._sanitize(str(exc)))
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc
        except Exception as exc:
            logger_calendar.error("Unexpected error fetching ICS from %s: %s", self._ics_url, exc)
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc

    @staticmethod
    def _sanitize(value: str) -> str:
        """Strip CR/LF to prevent log injection."""
        return str(value).replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _validate_url(url: str) -> None:
        """Reject URLs that could enable SSRF attacks.

        Only http/https schemes are allowed. The hostname must resolve to a
        public IP — private, loopback, link-local and multicast ranges are
        all rejected (covers RFC 1918, ::1, 169.254.x.x, etc.).
        """
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as exc:
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc

        if parsed.scheme not in ("http", "https"):
            logger_calendar.error("Rejected ICS URL with disallowed scheme: %s", parsed.scheme)
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)

        hostname: str | None = parsed.hostname
        if not hostname:
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)

        try:
            resolved = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            logger_calendar.error("Cannot resolve ICS hostname %s: %s", hostname, exc)
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc

        for info in resolved:
            ip_str: str = info[4][0].split("%")[0]  # strip IPv6 scope ID
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
                logger_calendar.error("Rejected ICS URL resolving to non-public address: %s", ip_str)
                raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)
