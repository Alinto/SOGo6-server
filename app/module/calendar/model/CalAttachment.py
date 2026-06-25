from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalAttachment:
    """
    File or URI attachment associated with a calendar event (RFC 5545 §3.8.1.1 ATTACH).

    Two forms: URI-based (url set, data None) and inline (data set, url None).
    Inline attachments use BASE64 encoding in iCalendar (RFC 5545 §3.2.7 ENCODING=BASE64).
    """
    # RFC 5545 §3.3.13 URI - remote resource; mutually exclusive with data
    url: str | None = None
    # RFC 5545 §3.2.8 FMTTYPE parameter - MIME type of the attachment (e.g. "application/pdf")
    filename: str | None = None
    mime_type: str | None = None
    # Byte size in octets - optional, implementation-specific
    size: int | None = None
    # Inline binary content - RFC 5545 §3.8.1.1 ATTACH;ENCODING=BASE64;VALUE=BINARY
    data: bytes | None = None
