from __future__ import annotations

from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.ContactDeserializerVcard import ContactDeserializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine


class ContactDeserializerVcard3(ContactDeserializerVcard):
    """Parse a vCard 3.0 card (RFC 2426) into a CardContact."""

    def version(self) -> str:
        return vc.VCARD_VERSION_3

    def import_format(self) -> ContactImportFormat:
        return ContactImportFormat.VCARD3

    def _decode_geo(self, value: str) -> str:
        # 3.0 GEO is "lat;lon"; turn it into the stored "geo:lat,lon" form.
        text: str = value.strip()
        return text if text.startswith(vc.GEO_URI_PREFIX) else vc.GEO_URI_PREFIX + text.replace(";", ",")

    def _parse_type_pref(self, content_line: ContentLine) -> tuple[list[str], int | None]:
        # 3.0: the preferred entry is the TYPE=pref value; a stray PREF parameter is a 4.0 fallback.
        raw_types: list[str] = content_line.param_values(vc.PARAM_TYPE)
        types: list[str] = [value for value in raw_types if value.lower() != "pref"]
        if len(types) != len(raw_types):
            return types, 1
        pref_param: str | None = content_line.first_param(vc.PARAM_PREF)
        return types, int(pref_param) if pref_param is not None and pref_param.isdigit() else None
