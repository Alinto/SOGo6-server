from __future__ import annotations

from typing import ClassVar


class MediaType:
    """Detect a media (MIME) type from the leading bytes of a payload (common images, SVG, PDF).

    Used where a format declares a photo's type unreliably or not at all (LDIF jpegPhoto is JPEG by
    name only; a vCard TYPE / data: URI mediatype can be missing or wrong): the bytes are
    authoritative. Only a handful of formats are recognised; an unknown one yields None so the
    caller keeps its declared fallback.
    """

    # Leading-byte signatures keyed to a media type (RIFF/WEBP is checked apart: its tag is at byte 8;
    # SVG is XML text with no binary magic, sniffed apart too).
    _SIGNATURES: ClassVar[tuple[tuple[bytes, str], ...]] = (
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
        (b"BM", "image/bmp"),
        (b"II*\x00", "image/tiff"),
        (b"MM\x00*", "image/tiff"),
        (b"%PDF-", "application/pdf"),
    )

    @staticmethod
    def get_content_type(data: bytes) -> str | None:
        """Return the media type recognised from data's magic number / markup, or None if unknown."""
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        for signature, media_type in MediaType._SIGNATURES:
            if data.startswith(signature):
                return media_type
        if MediaType._looks_like_svg(data):
            return "image/svg+xml"
        return None

    @staticmethod
    def _looks_like_svg(data: bytes) -> bool:
        """Whether data is an SVG document: XML/markup at the start with an <svg root in the head."""
        head: bytes = data[:1024]
        start: bytes = head.lstrip(b"\xef\xbb\xbf").lstrip()  # drop a UTF-8 BOM and leading whitespace
        return start.startswith((b"<svg", b"<?xml", b"<!--", b"<!DOCTYPE")) and b"<svg" in head
