from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CardAddress:  # pylint: disable=too-many-instance-attributes
    """Structured postal address of a contact (vCard ADR, RFC 6350 §6.3.1).

    Component order follows the ADR value: post-office box, extended address, street,
    locality, region, postal code, country.
    """
    po_box: str | None = None
    extended: str | None = None
    street: str | None = None
    locality: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None
    # TYPE parameter values (e.g. "home", "work")
    types: list[str] = field(default_factory=list)
    # PREF parameter (1-100, lower is preferred); None when unspecified
    pref: int | None = None
