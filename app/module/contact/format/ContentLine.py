from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContentLine:
    """A single parsed directory content line: [group.]NAME;PARAM=value...:VALUE (RFC 6350 §3.3).

    The common line model of every format handled by a FormatEngine. vCard is the rich case (group,
    parameters); LDIF is a subset where params is always empty and group is None - an LDIF
    "attr: value" is just a degenerate content line.

    name and parameter names are normalised to upper case (both are case-insensitive in vCard).
    params keeps every value of every parameter; a parameter may legitimately repeat or be a
    comma-list (TYPE), so each entry is a list. value is the raw (still escaped) property value.
    """
    name: str
    value: str = ""
    params: dict[str, list[str]] = field(default_factory=dict)
    group: str | None = None

    def first_param(self, name: str) -> str | None:
        """Return the first value of the named parameter (case-insensitive), or None when absent."""
        values = self.params.get(name.upper())
        return values[0] if values else None

    def param_values(self, name: str) -> list[str]:
        """Return every value of the named parameter (case-insensitive), in order."""
        return list(self.params.get(name.upper(), []))
