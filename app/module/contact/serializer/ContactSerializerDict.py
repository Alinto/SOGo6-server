from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.module.contact.serializer.CardAddressSerializerDict import CardAddressSerializerDict
from app.module.contact.serializer.CardEmailSerializerDict import CardEmailSerializerDict
from app.module.contact.serializer.CardImppSerializerDict import CardImppSerializerDict
from app.module.contact.serializer.CardPhoneSerializerDict import CardPhoneSerializerDict
from app.module.contact.serializer.CardUrlSerializerDict import CardUrlSerializerDict
from app.module.contact.serializer.ContactSerializer import ContactSerializer
from app.utils.datetime.DateTimeUtils import fmt_dt

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactSerializerDict(ContactSerializer[dict]):
    """Converts a CardContact to a plain dict matching the SOGo6 REST API schema.

    The same dict is reused by RepositoryContact as the persisted JSON blob, so it must carry
    every field needed to reconstruct the contact (the repository overrides the relational
    columns from their own values on read). Multi-valued sub-objects are delegated to their own
    serializers. Dates are ISO 8601: full datetimes as UTC with millisecond precision, BDAY /
    ANNIVERSARY as plain YYYY-MM-DD.
    """

    def __init__(self) -> None:
        self._email_serializer = CardEmailSerializerDict()
        self._phone_serializer = CardPhoneSerializerDict()
        self._address_serializer = CardAddressSerializerDict()
        self._url_serializer = CardUrlSerializerDict()
        self._impp_serializer = CardImppSerializerDict()

    def serialize(self, data: CardContact) -> dict[str, Any]:
        """Convert a CardContact to a plain dict matching the REST API schema."""
        return {
            "key": data.key,
            "addressbook_key": data.addressbook_key,
            "uid": data.uid,
            "version": data.version,
            "kind": data.kind.value,
            "display_name": data.display_name,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "middle_name": data.middle_name,
            "prefix": data.prefix,
            "suffix": data.suffix,
            "nickname": data.nickname,
            "organization": data.organization,
            "department": data.department,
            "job_title": data.job_title,
            "role": data.role,
            "emails": [self._email_serializer.serialize(e) for e in data.emails],
            "phones": [self._phone_serializer.serialize(p) for p in data.phones],
            "addresses": [self._address_serializer.serialize(a) for a in data.addresses],
            "urls": [self._url_serializer.serialize(u) for u in data.urls],
            "impp": [self._impp_serializer.serialize(i) for i in data.impp],
            "photos": data.photos,
            "categories": data.categories,
            "birthday": data.birthday.isoformat() if data.birthday else None,
            "anniversary": data.anniversary.isoformat() if data.anniversary else None,
            "geo": data.geo,
            "note": data.note,
            "public_key": data.public_key,
            "sound": data.sound,
            "timezone": data.timezone,
            "extra_properties": data.extra_properties,
            "import_format": data.import_format.value,
            "rev": fmt_dt(data.rev) if data.rev else None,
            "created_at": fmt_dt(data.created_at) if data.created_at else None,
            "updated_at": fmt_dt(data.updated_at) if data.updated_at else None,
        }
