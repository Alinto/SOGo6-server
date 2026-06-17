from __future__ import annotations

import base64
import binascii
from typing import ClassVar

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ContentLine import ContentLine
from app.module.contact.format.FormatEngine import FormatEngine


class FormatEngineLdif(FormatEngine):
    """LDIF syntax codec (RFC 2849): attribute parse/emit (base64 of non-safe values), record splitting.

    An LDIF line maps to a degenerate ContentLine (no params, no group); the value carries the
    decoded content. Line folding is inherited from FormatEngine. The serializers map
    CardContact/CardList onto the ContentLine attributes.
    """

    FOLD_LIMIT: ClassVar[int] = ld.LDIF_FOLD_LIMIT
    LINE_BREAK: ClassVar[str] = "\n"
    CONTINUATION_CHARS: ClassVar[tuple[str, ...]] = (" ",)

    #
    # Contract
    #
    @classmethod
    def split_items(cls, document: str) -> list[str]:
        """Split an LDIF document into record bodies (blank-line separated, comments / header dropped).

        An LDIF document holds several records (e.g. a whole address book). Comment lines (#), the
        version header and URL-valued lines (attr:< url, not fetched) are dropped here so each body
        contains only real attribute lines.
        """
        records: list[str] = []
        current: list[str] = []
        for line in cls.unfold(document):
            if not line.strip():
                if current:
                    records.append("\n".join(current))
                    current = []
                continue
            if line.startswith("#") or cls._is_header_or_url(line):
                continue
            current.append(line)
        if current:
            records.append("\n".join(current))
        return records

    @classmethod
    def parse_line(cls, line: str) -> ContentLine:
        """Parse one LDIF line into a ContentLine; base64 (`attr:: ...`) values are decoded."""
        colon: int = line.find(":")
        if colon == -1:
            return ContentLine(name=line)
        name: str = line[:colon]
        rest: str = line[colon + 1:]
        if rest.startswith(":"):
            payload: str = rest[1:].strip()
            try:
                decoded: bytes = base64.b64decode(payload)
            except (ValueError, binascii.Error):
                return ContentLine(name=name)
            try:
                value: str = decoded.decode("utf-8")
            except UnicodeDecodeError:
                value = payload  # binary attribute (e.g. jpegPhoto): keep the raw base64, lossless
        elif rest.startswith("<"):
            value = ""  # URL-valued, not fetched (also dropped by split_items)
        else:
            value = rest[1:] if rest.startswith(" ") else rest
        return ContentLine(name=name, value=value)

    @classmethod
    def emit_line(cls, content_line: ContentLine) -> str:
        """Render an attribute line, base64-encoding the value when it is not LDIF-safe."""
        if cls._is_safe(content_line.value):
            return cls.fold(f"{content_line.name}: {content_line.value}")
        encoded: str = base64.b64encode(content_line.value.encode("utf-8")).decode("ascii")
        return cls.fold(f"{content_line.name}:: {encoded}")

    #
    # LDIF-specific convenience over the contract (a record's lines have no params/group)
    #
    @classmethod
    def emit_attr(cls, name: str, value: str) -> str:
        """Emit a single attribute line (shorthand for emit_line of a bare ContentLine)."""
        return cls.emit_line(ContentLine(name=name, value=value))

    @classmethod
    def emit_attr_base64(cls, name: str, base64_payload: str) -> str:
        """Emit a binary attribute line (attr:: <payload>) from an already base64-encoded value.

        For binary attributes (e.g. jpegPhoto) whose payload is base64 text: emitting it through the
        text path would re-encode it as if it were the literal string. This writes the `::` form directly.
        """
        return cls.fold(f"{name}:: {base64_payload}")

    @classmethod
    def parse_records(cls, document: str) -> list[list[tuple[str, str]]]:
        """Parse a document into records, each a list of (attribute, value) pairs."""
        return [[(line.name, line.value) for line in cls.parse_item(body)] for body in cls.split_items(document)]

    @staticmethod
    def escape_dn(value: str) -> str:
        """Escape an attribute value for use in a distinguished name (RFC 4514 §2.4)."""
        escaped: str = value
        for char in ("\\", '"', "+", ",", ";", "<", ">"):
            escaped = escaped.replace(char, "\\" + char)
        if escaped[:1] in (" ", "#"):
            escaped = "\\" + escaped
        if escaped.endswith(" "):
            escaped = escaped[:-1] + "\\ "
        return escaped

    @staticmethod
    def unescape_dn(value: str) -> str:
        """Reverse escape_dn: drop the RFC 4514 backslash escaping from a DN attribute value."""
        result: list[str] = []
        index: int = 0
        while index < len(value):
            if value[index] == "\\" and index + 1 < len(value):
                result.append(value[index + 1])
                index += 2
            else:
                result.append(value[index])
                index += 1
        return "".join(result)

    #
    # Internal helpers
    #
    @staticmethod
    def _is_header_or_url(line: str) -> bool:
        """Whether a line is the version header (version:) or a URL-valued attribute (attr:< ...)."""
        colon: int = line.find(":")
        if colon == -1:
            return False
        if line[:colon].lower() == "version":
            return True
        return line[colon + 1:].startswith("<")

    @staticmethod
    def _is_safe(value: str) -> bool:
        """Whether value is an LDIF SAFE-STRING (no base64 needed): ASCII, no control chars, safe start."""
        if not value:
            return True
        if value[0] in (" ", ":", "<") or ord(value[0]) > 127:
            return False
        return all(ord(char) <= 127 and ord(char) not in (0, 10, 13) for char in value)
