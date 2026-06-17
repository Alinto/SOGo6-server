from __future__ import annotations

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif
from app.module.contact.model.CardAddress import CardAddress
from app.module.contact.model.CardContact import CardContact
from app.module.contact.model.CardEmail import CardEmail
from app.module.contact.model.CardPhone import CardPhone
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.ContactDeserializer import ContactDeserializer
from app.utils.uri.DataUri import DataUri


class ContactDeserializerLdif(ContactDeserializer[str]):
    """Parse the first LDIF record of a document into a CardContact (inetOrgPerson mapping)."""

    def deserialize(self, data: str) -> CardContact:
        records: list[list[tuple[str, str]]] = FormatEngineLdif.parse_records(data)
        return self.contact_from_pairs(records[0] if records else [])

    @staticmethod
    def contact_from_pairs(pairs: list[tuple[str, str]]) -> CardContact:  # pylint: disable=too-many-branches
        """Map a single LDIF record's (attribute, value) pairs onto a CardContact.

        Attributes outside the inetOrgPerson subset are kept in extra_properties (the contact's
        import_format=ldif tells they are LDIF attribute names); dn and objectClass are structural
        and dropped.
        """
        contact: CardContact = CardContact(import_format=ContactImportFormat.LDIF)
        address: CardAddress = CardAddress()
        has_address: bool = False
        for attr, value in pairs:
            name: str = attr.lower()
            if name in (ld.ATTR_DN.lower(), ld.ATTR_OBJECTCLASS.lower()):
                continue
            if name == ld.ATTR_DISPLAYNAME.lower() or (name == ld.ATTR_CN.lower() and not contact.display_name):
                contact.display_name = value
            elif name == ld.ATTR_SN.lower():
                contact.last_name = value
            elif name == ld.ATTR_GIVENNAME.lower():
                contact.first_name = value
            elif name == ld.ATTR_MAIL.lower():
                contact.emails.append(CardEmail(value=value))
            elif name == ld.ATTR_TELEPHONE.lower():
                contact.phones.append(CardPhone(number=value))
            elif name == ld.ATTR_MOBILE.lower():
                contact.phones.append(CardPhone(number=value, types=[ld.MOBILE_TYPE]))
            elif name == ld.ATTR_O.lower():
                contact.organization = value
            elif name == ld.ATTR_OU.lower():
                contact.department = value
            elif name == ld.ATTR_TITLE.lower():
                contact.job_title = value
            elif name == ld.ATTR_DESCRIPTION.lower():
                contact.note = value
            elif name == ld.ATTR_UID.lower():
                contact.uid = value
            elif name == ld.ATTR_JPEGPHOTO.lower():
                # value is the raw base64 of the binary attribute (kept undecoded by the engine). The
                # jpeg type here is nominal (a PNG in jpegPhoto stays mislabelled until the file layer
                # re-types it from the bytes when saved); only the stored form is authoritative.
                contact.photos.append(DataUri.wrap_base64(ld.JPEGPHOTO_MEDIA_TYPE, value))
            elif ContactDeserializerLdif._apply_address(address, name, value):
                has_address = True
            else:
                contact.extra_properties[attr] = value
        if has_address:
            contact.addresses.append(address)
        return contact

    @staticmethod
    def _apply_address(address: CardAddress, name: str, value: str) -> bool:
        """Set a postal-address attribute on the shared CardAddress; return True if it was one."""
        if name == ld.ATTR_STREET.lower():
            address.street = value
        elif name == ld.ATTR_L.lower():
            address.locality = value
        elif name == ld.ATTR_ST.lower():
            address.region = value
        elif name == ld.ATTR_POSTALCODE.lower():
            address.postal_code = value
        elif name == ld.ATTR_C.lower():
            address.country = value
        else:
            return False
        return True
