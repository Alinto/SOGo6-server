from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar

from app.module.contact.model.CardAddress import CardAddress
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardImpp import CardImpp
from app.module.contact.model.CardPhone import CardPhone
from app.module.contact.model.CardUrl import CardUrl
from app.module.contact.model.enums.CardKind import CardKind
from app.utils import errors as err
from app.utils.exceptions import BugException, RequestException
from app.utils.maths.sogo_hash import generate_uuid


@dataclass
class CardContact:  # pylint: disable=too-many-instance-attributes
    """Format-agnostic representation of a contact (vCard, RFC 6350).

    Once persisted a contact belongs to a single address book (addressbook_key), but the model
    itself is autonomous - it carries no address book by default, so the same object can also
    describe a directory entry that lives outside the user's books. Relational filter columns
    (last_name, first_name, organization, display_name, kind, uid) are derived from these fields
    by the repository; everything else is stored in the cal_contact JSON blob.

    Dates are real datetime.date objects: the vCard textual form (including partial dates) is the
    serializer's concern, not the model's.
    """
    # vCard UID (RFC 6350 §6.7.6) - stable semantic identifier
    uid: str | None = None
    # Opaque public identifier exposed in the API
    key: str | None = None
    # Internal database primary key
    db_id: int | None = None
    # UUID key of the parent address book - nullable: set by the source at persistence time
    addressbook_key: str | None = None
    # vCard VERSION (RFC 6350 §6.7.9)
    version: str = "4.0"
    # vCard KIND (RFC 6350 §6.1.4)
    kind: CardKind = CardKind.INDIVIDUAL

    # FN (RFC 6350 §6.2.1) - formatted display name; required by vCard, filled by apply_defaults
    display_name: str | None = None
    # N (RFC 6350 §6.2.2) - structured name components
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    # NICKNAME (RFC 6350 §6.2.3)
    nickname: str | None = None

    # ORG (RFC 6350 §6.6.4) - organization name and organizational unit
    organization: str | None = None
    department: str | None = None
    # TITLE (RFC 6350 §6.6.1) - job title
    job_title: str | None = None
    # ROLE (RFC 6350 §6.6.2)
    role: str | None = None

    emails: list[CardEmail] = field(default_factory=list)
    phones: list[CardPhone] = field(default_factory=list)
    addresses: list[CardAddress] = field(default_factory=list)
    urls: list[CardUrl] = field(default_factory=list)
    impp: list[CardImpp] = field(default_factory=list)
    # PHOTO (RFC 6350 §6.2.4) - URI only; embedded binary data is deliberately not supported
    photos: list[str] = field(default_factory=list)
    # CATEGORIES (RFC 6350 §6.7.1)
    categories: list[str] = field(default_factory=list)

    # BDAY / ANNIVERSARY (RFC 6350 §6.2.5 / §6.2.6)
    birthday: date | None = None
    anniversary: date | None = None
    # GEO (RFC 6350 §6.5.2) - "geo:lat,lon"
    geo: str | None = None
    # NOTE (RFC 6350 §6.7.2)
    note: str | None = None
    # KEY (RFC 6350 §6.8.1) - public key, stored as a URI
    public_key: str | None = None
    # SOUND (RFC 6350 §6.7.5) - URI
    sound: str | None = None
    # TZ (RFC 6350 §6.5.1)
    timezone: str | None = None

    # Catch-all for X-* and properties not mapped above - kept for lossless round-trip
    extra_properties: dict[str, str] = field(default_factory=dict)
    # REV (RFC 6350 §6.7.4) - revision timestamp
    rev: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    MUTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "display_name", "first_name", "last_name", "middle_name", "prefix", "suffix", "nickname",
        "kind", "organization", "department", "job_title", "role",
        "emails", "phones", "addresses", "urls", "impp", "photos", "categories",
        "birthday", "anniversary", "geo", "note", "public_key", "sound", "timezone", "extra_properties",
    })

    @property
    def require_uid(self) -> str:
        """vCard UID, guaranteed once apply_defaults has run / the contact has been loaded."""
        if self.uid is None:
            raise BugException("CardContact.uid accessed before it was generated")
        return self.uid

    @property
    def require_key(self) -> str:
        """Opaque public key, guaranteed once the contact has been persisted/loaded."""
        if self.key is None:
            raise BugException("CardContact.key accessed before the contact was persisted")
        return self.key

    def apply_defaults(self) -> None:
        """Fill in creation-time defaults: generate a UID and derive a display name when missing."""
        if not self.uid:
            self.uid = generate_uuid()
        if not self.display_name:
            self.display_name = self._derive_display_name()

    def _derive_display_name(self) -> str:
        """Build a formatted name (FN) from the structured name components, organization or nickname."""
        parts: list[str] = [p for p in (self.first_name, self.middle_name, self.last_name) if p]
        if parts:
            return " ".join(parts)
        return self.organization or self.nickname or "Unnamed Contact"

    def validate(self) -> None:
        """Run business validations. Raises RequestException on failure.

        vCard requires a non-empty FN; apply_defaults guarantees one, so an empty display_name
        here means the caller bypassed it.
        """
        if not self.display_name:
            raise RequestException(error=err.ERROR_CONTACT_JSON_PARSE_FAILED)
