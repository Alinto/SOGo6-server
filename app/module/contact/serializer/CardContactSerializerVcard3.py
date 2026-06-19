from __future__ import annotations

from app.module.contact.serializer.CardContactSerializerVcard import CardContactSerializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine
from app.utils.uri.DataUri import DataUri


class CardContactSerializerVcard3(CardContactSerializerVcard):
    """Serialize a CardContact to vCard 3.0 (RFC 2426)."""

    def version(self) -> str:
        return vc.VCARD_VERSION_3

    def _format_date(self, value: str) -> str:
        # 3.0 dates use the ISO extended form (RFC 2426); the canonical value is already extended.
        return value

    def _format_uid(self, uid: str) -> str:
        # 3.0 keeps the UID value as-is (Apple's X-ADDRESSBOOKSERVER convention uses the bare uid).
        return uid

    def _type_params(self, types: list[str], pref: int | None) -> dict[str, list[str]]:
        # 3.0 has no PREF parameter: the preferred entry is marked with the TYPE value "pref".
        values: list[str] = list(types)
        if pref is not None:
            values.append(vc.PARAM_VALUE_PREF)
        return {vc.PARAM_TYPE: values} if values else {}

    def _kind_lines(self, kind: str) -> list[ContentLine]:
        # 3.0 has no KIND property for individual contacts (groups use X-ADDRESSBOOKSERVER-KIND,
        # handled by the distribution-list serializer, not here).
        return []

    def _anniversary_name(self) -> str:
        return vc.PROP_X_ANNIVERSARY

    def _geo_value(self, geo: str) -> str:
        # 3.0 GEO is "lat;lon"; drop the 4.0 "geo:" URI prefix and swap the separator.
        coordinates: str = geo[len(vc.GEO_URI_PREFIX):] if geo.startswith(vc.GEO_URI_PREFIX) else geo
        return coordinates.replace(",", ";")

    def _photo_line(self, value: str) -> ContentLine:
        # 3.0 has no data: URI: an inline image uses ENCODING=b;TYPE=<subtype> with the base64 in the
        # value, an external one is flagged VALUE=uri (RFC 2426 §4).
        unwrapped: tuple[str, str] | None = DataUri.unwrap_base64(value)
        if unwrapped is None:
            return ContentLine(name=vc.PROP_PHOTO, value=value, params={vc.PARAM_VALUE: [vc.VALUE_URI]})
        content_type, payload = unwrapped
        return ContentLine(name=vc.PROP_PHOTO, value=payload,
                           params={vc.PARAM_ENCODING: [vc.ENCODING_BASE64],
                                   vc.PARAM_TYPE: [self._media_subtype(content_type)]})

    @staticmethod
    def _media_subtype(content_type: str) -> str:
        """The vCard 3.0 PHOTO TYPE token for a media type (image/jpeg -> JPEG)."""
        return content_type.split("/")[-1].upper()
