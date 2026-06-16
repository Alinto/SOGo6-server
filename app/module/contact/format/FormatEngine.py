from __future__ import annotations

from typing import ClassVar

from app.module.contact.format.ContentLine import ContentLine


class FormatEngine:
    """Common contract and shared syntax for a directory-format codec (vCard, LDIF, ...).

    A concrete engine owns the syntax of one format: it splits a document into item bodies (cards or
    records) and parses/emits a single line to/from a ContentLine. The line folding and unfolding
    shared by every MIME-DIR / LDIF format is implemented once here, parameterised by the two folding
    constants; a new format subclasses this engine, sets those constants and implements the three
    contract methods. Engines are stateless - every method is a classmethod.
    """

    # Subclasses MUST set these.
    FOLD_LIMIT: ClassVar[int] = 0          # max octets on a line before folding
    LINE_BREAK: ClassVar[str] = "\n"       # physical line separator emitted between folded lines
    CONTINUATION: ClassVar[str] = " "      # prefix added to a folded continuation line
    CONTINUATION_CHARS: ClassVar[tuple[str, ...]] = (" ",)  # prefixes recognised as a continuation on read

    #
    # Contract - each format implements these (a missing one raises at call time)
    #
    @classmethod
    def split_items(cls, document: str) -> list[str]:
        """Split a document into individual item bodies (a vCard card, an LDIF record)."""
        raise NotImplementedError(f"{cls.__name__} must implement split_items")

    @classmethod
    def parse_line(cls, line: str) -> ContentLine:
        """Parse one (already unfolded) line into a ContentLine."""
        raise NotImplementedError(f"{cls.__name__} must implement parse_line")

    @classmethod
    def emit_line(cls, content_line: ContentLine) -> str:
        """Render a ContentLine to a folded line of this format."""
        raise NotImplementedError(f"{cls.__name__} must implement emit_line")

    #
    # Shared - line folding (RFC 6350 §3.2 / RFC 2849) and item parsing
    #
    @classmethod
    def parse_item(cls, body: str) -> list[ContentLine]:
        """Unfold an item body and parse every non-empty line into a ContentLine."""
        return [cls.parse_line(line) for line in cls.unfold(body) if line.strip()]

    @classmethod
    def fold(cls, line: str) -> str:
        """Fold a logical line to at most FOLD_LIMIT octets, never splitting a UTF-8 character."""
        encoded: bytes = line.encode("utf-8")
        if len(encoded) <= cls.FOLD_LIMIT:
            return line
        chunks: list[bytes] = []
        start: int = 0
        limit: int = cls.FOLD_LIMIT
        while start < len(encoded):
            end: int = min(start + limit, len(encoded))
            while end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
                end -= 1
            chunks.append(encoded[start:end])
            start = end
            limit = cls.FOLD_LIMIT - len(cls.CONTINUATION)
        return (cls.LINE_BREAK + cls.CONTINUATION).join(chunk.decode("utf-8") for chunk in chunks)

    @classmethod
    def unfold(cls, text: str) -> list[str]:
        """Return the logical lines, joining continuation lines (prefixed by a CONTINUATION_CHARS char)."""
        logical: list[str] = []
        for physical in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if physical[:1] in cls.CONTINUATION_CHARS and logical:
                logical[-1] += physical[1:]
            else:
                logical.append(physical)
        return logical
