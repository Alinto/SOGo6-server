from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Any

from app.module.contact.ContactConst import DEFAULT_VCARD_VERSION
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.enums.CardKind import CardKind
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.CardAddressDeserializerDict import CardAddressDeserializerDict
from app.module.contact.serializer.CardEmailDeserializerDict import CardEmailDeserializerDict
from app.module.contact.serializer.CardImppDeserializerDict import CardImppDeserializerDict
from app.module.contact.serializer.CardPhoneDeserializerDict import CardPhoneDeserializerDict
from app.module.contact.serializer.CardUrlDeserializerDict import CardUrlDeserializerDict
from app.module.contact.serializer.ContactDeserializer import ContactDeserializer
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.logger.logger import logger_contact

_SKIP = object()


class ContactDeserializerDict(ContactDeserializer[dict]):
    """Deserializes plain dicts into CardContact objects.

    Fields absent from the dict keep the CardContact dataclass default. Multi-valued sub-objects
    are delegated to their own deserializers. The textual vCard date forms (partial dates) are the
    vCard deserializer's concern; here BDAY / ANNIVERSARY are full ISO dates (YYYY-MM-DD).
    """

    def __init__(self) -> None:
        self._email_deserializer = CardEmailDeserializerDict()
        self._phone_deserializer = CardPhoneDeserializerDict()
        self._address_deserializer = CardAddressDeserializerDict()
        self._url_deserializer = CardUrlDeserializerDict()
        self._impp_deserializer = CardImppDeserializerDict()

    def deserialize(self, data: dict[str, Any]) -> CardContact:
        """Convert a dict into a CardContact."""
        return CardContact(
            key=data.get("key"),
            addressbook_key=data.get("addressbook_key"),
            uid=data.get("uid"),
            version=data.get("version") or DEFAULT_VCARD_VERSION,
            kind=self._parse_kind(data.get("kind")),
            display_name=data.get("display_name"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            middle_name=data.get("middle_name"),
            prefix=data.get("prefix"),
            suffix=data.get("suffix"),
            nickname=data.get("nickname"),
            organization=data.get("organization"),
            department=data.get("department"),
            job_title=data.get("job_title"),
            role=data.get("role"),
            emails=[self._email_deserializer.deserialize(e) for e in data.get("emails", [])],
            phones=[self._phone_deserializer.deserialize(p) for p in data.get("phones", [])],
            addresses=[self._address_deserializer.deserialize(a) for a in data.get("addresses", [])],
            urls=[self._url_deserializer.deserialize(u) for u in data.get("urls", [])],
            impp=[self._impp_deserializer.deserialize(i) for i in data.get("impp", [])],
            photos=data.get("photos", []),
            categories=data.get("categories", []),
            birthday=self._parse_date(data.get("birthday")),
            anniversary=self._parse_date(data.get("anniversary")),
            geo=data.get("geo"),
            note=data.get("note"),
            public_key=data.get("public_key"),
            sound=data.get("sound"),
            timezone=data.get("timezone"),
            extra_properties=data.get("extra_properties", {}),
            import_format=self._parse_import_format(data.get("import_format")),
            rev=self._parse_dt_opt(data.get("rev")),
        )

    def deserialize_with_update(self, origin: CardContact, update: dict | CardContact) -> CardContact:
        """Apply a partial update to an existing CardContact and return the result.

        When update is a dict, parse each key and apply it to a copy of origin; only keys present
        in the dict are modified. Identity fields (uid, key, db_id, addressbook_key) and the
        server-managed version/rev are not in MUTABLE_FIELDS, so they are skipped here as well as
        re-asserted by ModuleContact.update_contact. When update is a CardContact, return it directly.
        """
        if isinstance(update, CardContact):
            return update

        merged: CardContact = dataclasses.replace(origin)
        for key, raw_value in update.items():
            parsed = self._parse_field(key, raw_value)
            if parsed is not _SKIP:
                setattr(merged, key, parsed)
        return merged

    def _parse_field(self, key: str, value: Any) -> Any:  # pylint: disable=too-many-return-statements
        """Parse a single update field. Returns _SKIP for unknown or immutable fields."""
        if key == "kind":
            return self._parse_kind(value)
        if key == "emails":
            return [self._email_deserializer.deserialize(e) for e in value]
        if key == "phones":
            return [self._phone_deserializer.deserialize(p) for p in value]
        if key == "addresses":
            return [self._address_deserializer.deserialize(a) for a in value]
        if key == "urls":
            return [self._url_deserializer.deserialize(u) for u in value]
        if key == "impp":
            return [self._impp_deserializer.deserialize(i) for i in value]
        if key in ("birthday", "anniversary"):
            return self._parse_date(value)
        if key in CardContact.MUTABLE_FIELDS:
            return value
        return _SKIP

    @staticmethod
    def _parse_kind(value: str | None) -> CardKind:
        """Parse a CardKind from its string value; fall back to INDIVIDUAL on missing or unknown."""
        if value is None:
            return CardKind.INDIVIDUAL
        try:
            return CardKind(value)
        except ValueError:
            logger_contact.warning("Unknown CardKind value %r, using INDIVIDUAL", value)
            return CardKind.INDIVIDUAL

    @staticmethod
    def _parse_import_format(value: str | None) -> ContactImportFormat:
        """Parse a ContactImportFormat from the blob; fall back to UNDEFINED on missing or unknown."""
        if value is None:
            return ContactImportFormat.UNDEFINED
        try:
            return ContactImportFormat(value)
        except ValueError:
            return ContactImportFormat.UNDEFINED

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        """Parse a full ISO date (YYYY-MM-DD); return None when absent."""
        return date.fromisoformat(value) if value else None

    @staticmethod
    def _parse_dt_opt(value: str | None) -> datetime | None:
        """Parse an optional ISO 8601 datetime string into UTC; return None when absent."""
        return to_utc(datetime.fromisoformat(value)) if value else None
