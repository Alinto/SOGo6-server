from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from app.module.contact.serializer.ContactSerializer import ContactSerializer
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine
from app.module.contact.format.vcard.VcardFormatEngine import VcardFormatEngine

if TYPE_CHECKING:
    from datetime import date

    from app.module.contact.model.CardAddress import CardAddress
    from app.module.contact.model.CardContact import CardContact


class ContactSerializerVcard(ContactSerializer[str], ABC):
    """Abstract base converting a CardContact to a vCard card (RFC 6350 / RFC 2426).

    The field mapping that is identical across versions lives here; the deltas between vCard 3.0 and
    4.0 (VERSION value, TYPE/PREF encoding, KIND, ANNIVERSARY name, GEO form) are delegated to the
    abstract hooks the concrete ContactSerializerVcard3 / ContactSerializerVcard4 implement.
    """

    def serialize(self, data: CardContact) -> str:
        """Render a CardContact to a complete BEGIN:VCARD ... END:VCARD block (CRLF-terminated)."""
        lines: list[ContentLine] = [
            ContentLine(name=vc.PROP_BEGIN, value=vc.VALUE_VCARD),
            ContentLine(name=vc.PROP_VERSION, value=self.version()),
        ]
        lines.extend(self._build_lines(data))
        lines.append(ContentLine(name=vc.PROP_END, value=vc.VALUE_VCARD))
        return "\r\n".join(VcardFormatEngine.emit_line(line) for line in lines) + "\r\n"

    #
    # Version-specific hooks
    #
    @abstractmethod
    def version(self) -> str:
        """The VERSION value emitted by this serializer ('3.0' or '4.0')."""

    @abstractmethod
    def _type_params(self, types: list[str], pref: int | None) -> dict[str, list[str]]:
        """Build the TYPE/PREF parameters for a typed property, in this version's encoding."""

    @abstractmethod
    def _kind_lines(self, kind: str) -> list[ContentLine]:
        """Lines expressing the contact KIND (a KIND property in 4.0, nothing in 3.0)."""

    @abstractmethod
    def _anniversary_name(self) -> str:
        """Property name used for the anniversary date (ANNIVERSARY in 4.0, X-ANNIVERSARY in 3.0)."""

    @abstractmethod
    def _geo_value(self, geo: str) -> str:
        """The GEO property value in this version's form."""

    @abstractmethod
    def _format_date(self, value: date) -> str:
        """Format a BDAY / ANNIVERSARY date: basic (YYYYMMDD) in 4.0, extended (RFC 2426) in 3.0."""

    @abstractmethod
    def _format_uid(self, uid: str) -> str:
        """Render the UID value: a urn:uuid: URI in 4.0, the bare value in 3.0."""

    #
    # Common mapping
    #
    def _build_lines(self, c: CardContact) -> list[ContentLine]:  # pylint: disable=too-many-branches
        """Build every property line of the card except BEGIN/VERSION/END."""
        lines: list[ContentLine] = list(self._kind_lines(c.kind.value))
        lines.append(self._text_line(vc.PROP_FN, c.display_name or ""))
        lines.append(self._structured_line(
            vc.PROP_N, [c.last_name, c.first_name, c.middle_name, c.prefix, c.suffix]))
        if c.nickname:
            lines.append(self._text_line(vc.PROP_NICKNAME, c.nickname))
        if c.organization or c.department:
            lines.append(self._structured_line(vc.PROP_ORG, [c.organization, c.department]))
        if c.job_title:
            lines.append(self._text_line(vc.PROP_TITLE, c.job_title))
        if c.role:
            lines.append(self._text_line(vc.PROP_ROLE, c.role))
        for email in c.emails:
            lines.append(self._typed_line(vc.PROP_EMAIL, email.value, email.types, email.pref))
        for phone in c.phones:
            lines.append(self._typed_line(vc.PROP_TEL, phone.number, phone.types, phone.pref))
        for address in c.addresses:
            lines.append(self._adr_line(address))
        for url in c.urls:
            lines.append(self._typed_line(vc.PROP_URL, url.value, self._single_type(url.type), None))
        for impp in c.impp:
            lines.append(self._typed_line(vc.PROP_IMPP, impp.uri, self._single_type(impp.type), None))
        if c.categories:
            lines.append(ContentLine(
                name=vc.PROP_CATEGORIES,
                value=",".join(VcardFormatEngine.escape_text(category) for category in c.categories)))
        if c.note:
            lines.append(self._text_line(vc.PROP_NOTE, c.note))
        if c.birthday:
            lines.append(ContentLine(name=vc.PROP_BDAY, value=self._format_date(c.birthday)))
        if c.anniversary:
            lines.append(ContentLine(name=self._anniversary_name(), value=self._format_date(c.anniversary)))
        if c.geo:
            lines.append(ContentLine(name=vc.PROP_GEO, value=self._geo_value(c.geo)))
        if c.public_key:
            lines.append(ContentLine(name=vc.PROP_KEY, value=c.public_key))
        if c.sound:
            lines.append(ContentLine(name=vc.PROP_SOUND, value=c.sound))
        if c.timezone:
            lines.append(self._text_line(vc.PROP_TZ, c.timezone))
        for photo in c.photos:
            lines.append(ContentLine(name=vc.PROP_PHOTO, value=photo))
        if c.uid:
            lines.append(ContentLine(name=vc.PROP_UID, value=self._format_uid(c.uid)))
        if c.rev:
            lines.append(ContentLine(name=vc.PROP_REV, value=self._format_timestamp(c.rev)))
        for name, value in c.extra_properties.items():
            lines.append(self._text_line(name, value))
        return lines

    #
    # Line builders shared by the versions
    #
    @staticmethod
    def _text_line(name: str, value: str) -> ContentLine:
        """A TEXT-valued property: the value is escaped (RFC 6350 §3.4)."""
        return ContentLine(name=name, value=VcardFormatEngine.escape_text(value))

    @staticmethod
    def _structured_line(name: str, components: list[str | None], params: dict[str, list[str]] | None = None) -> ContentLine:
        """A structured property (N, ORG, ADR): components escaped and joined by ';'."""
        rendered: str = ";".join(VcardFormatEngine.escape_text(component or "") for component in components)
        return ContentLine(name=name, value=rendered, params=params or {})

    def _typed_line(self, name: str, value: str, types: list[str], pref: int | None) -> ContentLine:
        """A URI/addr property carrying TYPE/PREF (EMAIL, TEL, URL, IMPP): value kept verbatim."""
        return ContentLine(name=name, value=value, params=self._type_params(types, pref))

    def _adr_line(self, address: CardAddress) -> ContentLine:
        """An ADR property: 7 structured components plus TYPE/PREF parameters."""
        return self._structured_line(
            vc.PROP_ADR,
            [address.po_box, address.extended, address.street, address.locality,
             address.region, address.postal_code, address.country],
            params=self._type_params(address.types, address.pref))

    @staticmethod
    def _single_type(value: str | None) -> list[str]:
        """Wrap a single optional TYPE value into the list shape the typed-line helper expects."""
        return [value] if value else []

    @staticmethod
    def _format_timestamp(moment: datetime) -> str:
        """Format a REV timestamp as the vCard basic UTC form YYYYMMDDTHHMMSSZ."""
        return moment.strftime("%Y%m%dT%H%M%SZ")
