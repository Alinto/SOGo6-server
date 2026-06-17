from __future__ import annotations

from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.ContactDeserializerVcard import ContactDeserializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine


class ContactDeserializerVcard4(ContactDeserializerVcard):
    """Parse a vCard 4.0 card (RFC 6350) into a CardContact."""

    def version(self) -> str:
        return vc.VCARD_VERSION_4

    def import_format(self) -> ContactImportFormat:
        return ContactImportFormat.VCARD4

    def _decode_geo(self, value: str) -> str:
        # 4.0 GEO is already the stored "geo:lat,lon" URI form.
        return value.strip()

    def _parse_photo(self, line: ContentLine) -> str:
        # 4.0 PHOTO is already a URI (external or data:); keep it verbatim.
        return line.value

    def _parse_type_pref(self, content_line: ContentLine) -> tuple[list[str], int | None]:
        # 4.0: the PREF parameter is authoritative; a TYPE=pref is tolerated as a fallback.
        types: list[str] = [value for value in content_line.param_values(vc.PARAM_TYPE) if value.lower() != "pref"]
        pref_param: str | None = content_line.first_param(vc.PARAM_PREF)
        if pref_param is not None and pref_param.isdigit():
            return types, int(pref_param)
        had_pref_type: bool = len(types) != len(content_line.param_values(vc.PARAM_TYPE))
        return types, 1 if had_pref_type else None
