from __future__ import annotations

from enum import Enum


class ContactExportFormat(Enum):
    """A supported export serialization, with the media type and file extension it produces."""

    VCARD4 = ("text/vcard; charset=utf-8; version=4.0", "vcf")
    VCARD3 = ("text/vcard; charset=utf-8; version=3.0", "vcf")
    LDIF = ("text/ldif; charset=utf-8", "ldif")
    JSON = ("application/json; charset=utf-8", "json")

    def __init__(self, media_type: str, extension: str) -> None:
        self.media_type: str = media_type
        self.extension: str = extension
