from __future__ import annotations

import base64
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

from app.module.calendar.CalendarConst import FETCH_TIMEOUT_SECONDS, MAX_ICS_BYTES, MAX_ICS_REDIRECTS
from app.utils.errors import ERROR_CALENDAR_ICS_FETCH_FAILED, ERROR_CALENDAR_ICS_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar


class _LimitedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP redirect handler that limits the number of redirects to prevent redirect loops."""

    def __init__(self, max_redirects: int) -> None:
        super().__init__()
        self._max = max_redirects
        self._count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self._count += 1
        if self._count > self._max:
            logger_calendar.error("ICS feed exceeded max redirects (%d)", self._max)
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class IcsFetcher:
    """Downloads ICS content from a remote URL with SSRF protection.

    Validates the URL scheme (http/https only) and rejects private/loopback/link-local IPs.
    Enforces a size limit, timeout, and redirect limit on the download.
    Supports HTTP Basic authentication for htaccess-protected feeds.
    """

    @staticmethod
    def fetch(url: str, username: str | None = None, password: str | None = None) -> str:
        """Download and return the ICS content as a string.

        :param url: The remote ICS URL to fetch.
        :param username: Optional HTTP Basic auth username.
        :param password: Optional HTTP Basic auth password.
        :raises RequestException: On network error, invalid URL, SSRF attempt, size limit exceeded, or invalid ICS format.
        """
        IcsFetcher._validate_url(url)
        logger_calendar.debug("Fetching ICS from %s", url)
        try:
            request = urllib.request.Request(url)
            if username and password:
                credentials: str = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
                request.add_header("Authorization", f"Basic {credentials}")

            opener = urllib.request.build_opener(_LimitedRedirectHandler(max_redirects=MAX_ICS_REDIRECTS))
            with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                raw: bytes = response.read(MAX_ICS_BYTES + 1)
                if len(raw) > MAX_ICS_BYTES:
                    logger_calendar.error("ICS feed from %s exceeds size limit (%d bytes)", url, MAX_ICS_BYTES)
                    raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)
                try:
                    text: str = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("latin-1")

            IcsFetcher._validate_ics_format(text, url)
            return text
        except RequestException:
            raise
        except urllib.error.HTTPError as exc:
            logger_calendar.error("HTTP %s fetching ICS from %s: %s", exc.code, url, IcsFetcher._sanitize(exc.reason))
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc
        except urllib.error.URLError as exc:
            logger_calendar.error("Failed to fetch ICS from %s: %s", url, IcsFetcher._sanitize(str(exc)))
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc
        except Exception as exc:
            logger_calendar.error("Unexpected error fetching ICS from %s: %s", url, exc)
            raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED) from exc

    @staticmethod
    def _validate_ics_format(text: str, url: str) -> None:
        """Validate that the content looks like a valid iCalendar feed."""
        if "BEGIN:VCALENDAR" not in text:
            logger_calendar.error("ICS feed from %s is not a valid iCalendar (missing BEGIN:VCALENDAR)", url)
            raise RequestException(error=ERROR_CALENDAR_ICS_PARSE_FAILED)

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
            ip_str: str = info[4][0].split("%")[0]
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
                logger_calendar.error("Rejected ICS URL resolving to non-public address: %s", ip_str)
                raise RequestException(error=ERROR_CALENDAR_ICS_FETCH_FAILED)
