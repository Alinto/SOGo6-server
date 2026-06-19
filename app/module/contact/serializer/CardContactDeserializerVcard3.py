from __future__ import annotations

from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.CardContactDeserializerVcard import CardContactDeserializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine
from app.utils.uri.DataUri import DataUri


class CardContactDeserializerVcard3(CardContactDeserializerVcard):
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

    def _parse_photo(self, line: ContentLine) -> str:
        # 3.0 inline image: ENCODING=b with base64 in the value -> data: URI typed from the TYPE token;
        # a plain-URI PHOTO is kept as-is.
        encoding: str | None = line.first_param(vc.PARAM_ENCODING)
        if encoding is not None and encoding.lower() in (vc.ENCODING_BASE64, vc.ENCODING_BASE64_ALT):
            return DataUri.wrap_base64(self._media_type(line.first_param(vc.PARAM_TYPE)), line.value)
        return line.value

    @staticmethod
    def _media_type(type_token: str | None) -> str:
        """The media type for a vCard 3.0 PHOTO TYPE token (JPEG -> image/jpeg); a default when absent."""
        return f"image/{type_token.lower()}" if type_token else vc.PHOTO_DEFAULT_MEDIA_TYPE
