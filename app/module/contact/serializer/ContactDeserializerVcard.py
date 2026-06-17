from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from app.module.contact.ContactConst import DEFAULT_VCARD_VERSION
from app.module.contact.model.CardAddress import CardAddress
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardImpp import CardImpp
from app.module.contact.model.CardPhone import CardPhone
from app.module.contact.model.CardUrl import CardUrl
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.ContactDeserializer import ContactDeserializer
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine
from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.logger.logger import logger_contact


class ContactDeserializerVcard(ContactDeserializer[str], ABC):
    """Abstract base parsing a vCard card into a CardContact (RFC 6350 / RFC 2426).

    The parsing that does not depend on the version lives here; the only per-version decode is the
    TYPE/PREF extraction, delegated to the concrete ContactDeserializerVcard3 / ContactDeserializerVcard4.
    detect_version reads the card's VERSION so the caller can pick the right subclass. The reader is
    lenient: an unknown or malformed property is kept in extra_properties rather than raising.
    """

    @staticmethod
    def detect_version(raw: str) -> str:
        """Return the VERSION declared in the card ('3.0' / '4.0'), or DEFAULT_VCARD_VERSION if absent."""
        for content_line in FormatEngineVcard.parse_item(raw):
            if content_line.name == vc.PROP_VERSION:
                value: str = content_line.value.strip()
                return value if value in (vc.VCARD_VERSION_3, vc.VCARD_VERSION_4) else DEFAULT_VCARD_VERSION
        return DEFAULT_VCARD_VERSION

    @staticmethod
    def is_group_card(raw: str) -> bool:
        """Whether a card is a distribution list (KIND:group, 4.0, or X-ADDRESSBOOKSERVER-KIND:group, 3.0)."""
        for content_line in FormatEngineVcard.parse_item(raw):
            if content_line.name in (vc.PROP_KIND, vc.PROP_X_ABS_KIND) and content_line.value.strip().lower() == vc.KIND_GROUP:
                return True
        return False

    @abstractmethod
    def version(self) -> str:
        """The vCard version this deserializer targets (fallback when the card omits VERSION)."""

    @abstractmethod
    def import_format(self) -> ContactImportFormat:
        """The provenance stamp for cards read by this version (VCARD3 / VCARD4)."""

    @abstractmethod
    def _parse_type_pref(self, content_line: ContentLine) -> tuple[list[str], int | None]:
        """Extract the TYPE values and the PREF rank from a typed property, in this version's encoding."""

    @abstractmethod
    def _decode_geo(self, value: str) -> str:
        """Decode a GEO value into the stored 'geo:lat,lon' form, in this version's encoding."""

    @abstractmethod
    def _parse_photo(self, line: ContentLine) -> str:
        """Decode a PHOTO into the stored form (a data: URI for inline images, a plain URI otherwise)."""

    def deserialize(self, data: str) -> CardContact:  # pylint: disable=too-many-branches,too-many-statements
        """Parse a single vCard card into a CardContact."""
        contact: CardContact = CardContact(version=self.version(), import_format=self.import_format())
        for line in FormatEngineVcard.parse_item(data):
            name: str = line.name
            if name in (vc.PROP_BEGIN, vc.PROP_END):
                continue
            if name == vc.PROP_VERSION:
                contact.version = line.value.strip() or self.version()
            elif name == vc.PROP_FN:
                contact.display_name = FormatEngineVcard.unescape_text(line.value)
            elif name == vc.PROP_N:
                self._apply_name(contact, line.value)
            elif name == vc.PROP_NICKNAME:
                contact.nickname = FormatEngineVcard.unescape_text(line.value)
            elif name == vc.PROP_KIND:
                contact.kind = self._parse_kind(line.value)
            elif name == vc.PROP_ORG:
                self._apply_org(contact, line.value)
            elif name == vc.PROP_TITLE:
                contact.job_title = FormatEngineVcard.unescape_text(line.value)
            elif name == vc.PROP_ROLE:
                contact.role = FormatEngineVcard.unescape_text(line.value)
            elif name == vc.PROP_EMAIL:
                types, pref = self._parse_type_pref(line)
                contact.emails.append(CardEmail(value=line.value, types=types, pref=pref))
            elif name == vc.PROP_TEL:
                types, pref = self._parse_type_pref(line)
                contact.phones.append(CardPhone(number=self._strip_prefix(line.value, vc.TEL_URI_PREFIX),
                                                types=types, pref=pref))
            elif name == vc.PROP_ADR:
                contact.addresses.append(self._parse_adr(line))
            elif name == vc.PROP_URL:
                contact.urls.append(CardUrl(value=line.value, type=self._first_type(line)))
            elif name == vc.PROP_IMPP:
                contact.impp.append(CardImpp(uri=line.value, type=self._first_type(line)))
            elif name == vc.PROP_CATEGORIES:
                contact.categories = [FormatEngineVcard.unescape_text(part) for part in FormatEngineVcard.split_values(line.value)]
            elif name == vc.PROP_NOTE:
                contact.note = FormatEngineVcard.unescape_text(line.value)
            elif name == vc.PROP_BDAY:
                contact.birthday = self._parse_date(line.value)
            elif name in (vc.PROP_ANNIVERSARY, vc.PROP_X_ANNIVERSARY):
                contact.anniversary = self._parse_date(line.value)
            elif name == vc.PROP_GEO:
                contact.geo = self._decode_geo(line.value)
            elif name == vc.PROP_KEY:
                contact.public_key = line.value
            elif name == vc.PROP_SOUND:
                contact.sound = line.value
            elif name == vc.PROP_TZ:
                contact.timezone = FormatEngineVcard.unescape_text(line.value)
            elif name == vc.PROP_PHOTO:
                contact.photos.append(self._parse_photo(line))
            elif name == vc.PROP_UID:
                contact.uid = self._strip_prefix(line.value, vc.UID_URN_PREFIX)
            elif name == vc.PROP_REV:
                contact.rev = self._parse_timestamp(line.value)
            else:
                contact.extra_properties[name] = FormatEngineVcard.unescape_text(line.value)
        return contact

    #
    # Field parsers
    #
    @staticmethod
    def _apply_name(contact: CardContact, value: str) -> None:
        """Map the N structured value (family;given;additional;prefixes;suffixes) onto the contact."""
        parts: list[str | None] = [
            FormatEngineVcard.unescape_text(part) or None for part in FormatEngineVcard.split_components(value)]
        parts += [None] * (5 - len(parts))
        contact.last_name, contact.first_name, contact.middle_name, contact.prefix, contact.suffix = parts[:5]

    @staticmethod
    def _apply_org(contact: CardContact, value: str) -> None:
        """Map the ORG structured value (organization;unit) onto the contact."""
        parts: list[str] = FormatEngineVcard.split_components(value)
        contact.organization = FormatEngineVcard.unescape_text(parts[0]) or None if parts else None
        contact.department = FormatEngineVcard.unescape_text(parts[1]) or None if len(parts) > 1 else None

    def _parse_adr(self, line: ContentLine) -> CardAddress:
        """Map an ADR structured value + TYPE/PREF parameters onto a CardAddress."""
        parts: list[str | None] = [
            FormatEngineVcard.unescape_text(part) or None for part in FormatEngineVcard.split_components(line.value)]
        parts += [None] * (7 - len(parts))
        types, pref = self._parse_type_pref(line)
        return CardAddress(po_box=parts[0], extended=parts[1], street=parts[2], locality=parts[3],
                           region=parts[4], postal_code=parts[5], country=parts[6], types=types, pref=pref)

    @staticmethod
    def _first_type(line: ContentLine) -> str | None:
        """First TYPE value of a single-typed property (URL, IMPP), or None."""
        return line.first_param(vc.PARAM_TYPE)

    @staticmethod
    def _parse_kind(value: str) -> CardKind:
        """Parse a CardKind, defaulting to INDIVIDUAL on an unknown value."""
        try:
            return CardKind(value.strip().lower())
        except ValueError:
            logger_contact.warning("Unknown vCard KIND value %r, using INDIVIDUAL", value)
            return CardKind.INDIVIDUAL

    @staticmethod
    def _parse_date(value: str) -> date | None:
        """Parse a vCard date (ISO extended 1985-04-12 or basic 19850412); None on partial/text forms."""
        text: str = value.strip()
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        """Parse a REV timestamp (vCard basic or ISO 8601) into an aware UTC datetime, or None."""
        text: str = value.strip().replace("Z", "+0000")
        for fmt in ("%Y%m%dT%H%M%S%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return to_utc(datetime.strptime(text, fmt))
            except ValueError:
                continue
        return None

    @staticmethod
    def _strip_prefix(value: str, prefix: str) -> str:
        """Drop a leading URI prefix (case-insensitive) such as 'tel:' or 'urn:uuid:'."""
        return value[len(prefix):] if value.lower().startswith(prefix.lower()) else value
