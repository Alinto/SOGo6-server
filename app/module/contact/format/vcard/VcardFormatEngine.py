from __future__ import annotations

from typing import ClassVar

from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine
from app.module.contact.format.FormatEngine import FormatEngine


class VcardFormatEngine(FormatEngine):
    """vCard syntax codec (RFC 6350 §3): content-line parse/emit, escaping, card splitting.

    Owns only the vCard syntax - it knows no property name nor version. The serializers map
    CardContact/CardList onto (and from) the ContentLine objects it produces. The line folding is
    inherited from FormatEngine.
    """

    FOLD_LIMIT: ClassVar[int] = vc.VCARD_FOLD_LIMIT
    LINE_BREAK: ClassVar[str] = "\r\n"
    CONTINUATION_CHARS: ClassVar[tuple[str, ...]] = (" ", "\t")

    #
    # Contract
    #
    @classmethod
    def split_items(cls, document: str) -> list[str]:
        """Split a .vcf document into card bodies (lines between BEGIN:VCARD and END:VCARD).

        BEGIN/END delimiters are dropped; every other property line (including VERSION) is kept. A
        body is returned as its logical lines joined by CRLF; text outside a BEGIN/END pair is ignored.
        """
        cards: list[str] = []
        current: list[str] | None = None
        for line in cls.unfold(document):
            marker: str = line.strip().upper()
            if marker == "BEGIN:VCARD":
                current = []
            elif marker == "END:VCARD":
                if current is not None:
                    cards.append("\r\n".join(current))
                current = None
            elif current is not None:
                current.append(line)
        return cards

    @classmethod
    def parse_line(cls, line: str) -> ContentLine:
        """Parse one (already unfolded) content line into a ContentLine.

        Splits on the first colon outside a quoted parameter value, then breaks the head into an
        optional group, the property name and the parameters. A bare parameter without '=' (the
        vCard 2.1 / 3.0 shorthand, e.g. TEL;WORK) is recorded as a TYPE value.
        """
        head, value = cls._split_on_value_colon(line)
        segments: list[str] = cls._split_unquoted(head, ";")
        name_part: str = segments[0].strip()
        group: str | None = None
        if "." in name_part:
            group, name_part = name_part.split(".", 1)
        params: dict[str, list[str]] = {}
        for raw in segments[1:]:
            if not raw.strip():
                continue
            if "=" in raw:
                pname, pvalue = raw.split("=", 1)
                key: str = pname.strip().upper()
                values: list[str] = [cls._strip_quotes(part) for part in cls._split_unquoted(pvalue, ",")]
            else:
                key, values = "TYPE", [cls._strip_quotes(raw.strip())]
            params.setdefault(key, []).extend(values)
        return ContentLine(name=name_part.upper(), value=value, params=params, group=group)

    @classmethod
    def emit_line(cls, content_line: ContentLine) -> str:
        """Render a ContentLine to a folded vCard line. Parameter values are quoted when needed."""
        head: str = content_line.name if content_line.group is None else f"{content_line.group}.{content_line.name}"
        for pname, values in content_line.params.items():
            rendered: str = ",".join(cls._quote_param(value) for value in values)
            head += f";{pname}={rendered}"
        return cls.fold(f"{head}:{content_line.value}")

    #
    # vCard-specific value handling (not part of the FormatEngine contract)
    #
    @staticmethod
    def escape_text(value: str) -> str:
        """Escape a TEXT value: backslash, newline, comma and semicolon (RFC 6350 §3.4)."""
        return (value.replace("\\", "\\\\").replace("\n", "\\n")
                .replace(",", "\\,").replace(";", "\\;"))

    @staticmethod
    def unescape_text(value: str) -> str:
        """Reverse escape_text, tolerating an unknown escape by keeping the escaped character."""
        out: list[str] = []
        index: int = 0
        while index < len(value):
            char: str = value[index]
            if char == "\\" and index + 1 < len(value):
                nxt: str = value[index + 1]
                out.append("\n" if nxt in ("n", "N") else nxt)
                index += 2
            else:
                out.append(char)
                index += 1
        return "".join(out)

    @staticmethod
    def split_components(value: str) -> list[str]:
        """Split a structured value (N, ADR) on unescaped semicolons. Parts stay escaped."""
        return VcardFormatEngine._split_escaped(value, ";")

    @staticmethod
    def split_values(value: str) -> list[str]:
        """Split a multi-value (CATEGORIES) on unescaped commas. Parts stay escaped."""
        return VcardFormatEngine._split_escaped(value, ",")

    #
    # Internal helpers
    #
    @staticmethod
    def _split_on_value_colon(line: str) -> tuple[str, str]:
        """Split a line into (head, value) on the first colon outside a quoted parameter value."""
        in_quote: bool = False
        for index, char in enumerate(line):
            if char == '"':
                in_quote = not in_quote
            elif char == ":" and not in_quote:
                return line[:index], line[index + 1:]
        return line, ""

    @staticmethod
    def _split_unquoted(text: str, separator: str) -> list[str]:
        """Split text on separator, ignoring separators inside double quotes."""
        parts: list[str] = []
        current: list[str] = []
        in_quote: bool = False
        for char in text:
            if char == '"':
                in_quote = not in_quote
                current.append(char)
            elif char == separator and not in_quote:
                parts.append("".join(current))
                current = []
            else:
                current.append(char)
        parts.append("".join(current))
        return parts

    @staticmethod
    def _split_escaped(value: str, separator: str) -> list[str]:
        """Split value on separator, skipping backslash-escaped separators."""
        parts: list[str] = []
        current: list[str] = []
        index: int = 0
        while index < len(value):
            char: str = value[index]
            if char == "\\" and index + 1 < len(value):
                current.append(char)
                current.append(value[index + 1])
                index += 2
            elif char == separator:
                parts.append("".join(current))
                current = []
                index += 1
            else:
                current.append(char)
                index += 1
        parts.append("".join(current))
        return parts

    @staticmethod
    def _strip_quotes(value: str) -> str:
        """Remove the surrounding double quotes of a parameter value when present."""
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value

    @staticmethod
    def _quote_param(value: str) -> str:
        """Wrap a parameter value in double quotes when it contains a colon, semicolon or comma."""
        return f'"{value}"' if any(char in value for char in ':;,') else value
