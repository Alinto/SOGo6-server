from __future__ import annotations

import base64


class DataUri:
    """Parser and builder for base64 RFC 2397 data URIs (data:<mediatype>;base64,<payload>).

    Only the base64 form is handled - the one carried by vCard PHOTO/LOGO values and the JSON
    contact payloads. A value that is not a base64 data URI is reported as unparseable (None).
    """

    PREFIX: str = "data:"
    BASE64_MARKER: str = ";base64"

    @staticmethod
    def unwrap_base64(value: str) -> tuple[str, str] | None:
        """Split a base64 data URI into (content_type, base64 payload) without decoding, or None.

        Useful to move the payload between data URIs and the base64 forms of other formats (vCard
        3.0 ENCODING=b, LDIF jpegPhoto) without a decode/re-encode round-trip.
        """
        if not value.startswith(DataUri.PREFIX) or "," not in value:
            return None
        meta, _, payload = value[len(DataUri.PREFIX):].partition(",")
        if not meta.endswith(DataUri.BASE64_MARKER):
            return None
        return meta[: -len(DataUri.BASE64_MARKER)], payload

    @staticmethod
    def wrap_base64(content_type: str, base64_payload: str) -> str:
        """Assemble a data URI from a content type and an already base64-encoded payload."""
        return f"{DataUri.PREFIX}{content_type}{DataUri.BASE64_MARKER},{base64_payload}"

    @staticmethod
    def parse(value: str) -> tuple[str, bytes] | None:
        """Return (content_type, raw bytes) for a base64 data URI, or None when value is not one."""
        unwrapped: tuple[str, str] | None = DataUri.unwrap_base64(value)
        if unwrapped is None:
            return None
        content_type, payload = unwrapped
        try:
            return content_type, base64.b64decode(payload, validate=True)
        except ValueError:
            return None

    @staticmethod
    def build(content_type: str, data: bytes) -> str:
        """Build a base64 data URI from a content type and raw bytes."""
        return DataUri.wrap_base64(content_type, base64.b64encode(data).decode("ascii"))
