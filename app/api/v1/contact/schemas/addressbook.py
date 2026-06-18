from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class AddressBookCreateSchema(Schema):
    """Request body for creating an address book."""

    name        = fields.String(required=True, validate=validate.Length(min=1, max=255),
                                metadata={"example": "Personal contacts"})
    description = fields.String(load_default=None, allow_none=True,
                                metadata={"example": "My personal address book"})


class AddressBookUpdateSchema(Schema):
    """Request body for updating an address book (all fields optional)."""

    name        = fields.String(validate=validate.Length(min=1, max=255), metadata={"example": "Friends"})
    description = fields.String(allow_none=True)
    is_default  = fields.Boolean(metadata={"description": "Mark this book as the user's default address book."})


class CardAddressBookSchema(Schema):
    """Representation of an address book in API responses."""

    key         = fields.String()
    name        = fields.String()
    description = fields.String(allow_none=True)
    is_default  = fields.Boolean()
    source_type = fields.String()
    ctag        = fields.Integer(metadata={"description": "CardDAV change tag, bumped on every contact mutation."})


class AddressBookListDataSchema(Schema):
    """Data payload for the address book list response."""

    addressbooks = fields.List(fields.Nested(CardAddressBookSchema))
    total_count  = fields.Integer()


class AddressBookListResponseSchema(ApiBaseResponse):
    """Response schema for a list of address books."""

    data = fields.Nested(AddressBookListDataSchema, allow_none=True)


class AddressBookResponseSchema(ApiBaseResponse):
    """Response schema for a single address book."""

    data = fields.Nested(CardAddressBookSchema, allow_none=True)


class ContactImportQueryArgsSchema(Schema):
    """Query arguments for the import endpoints."""

    format = fields.String(load_default="json", validate=validate.OneOf(["json", "vcard3", "vcard4", "ldif"]),
                           metadata={"description": "Source format of the uploaded document (default json)."})


class ContactImportResultDataSchema(Schema):
    """Counters returned after an import (address book key/name set only on a whole-book import)."""

    contacts_inserted = fields.Integer()
    contacts_updated  = fields.Integer()
    lists_inserted    = fields.Integer()
    lists_updated     = fields.Integer()
    skipped           = fields.Integer()
    addressbook_key   = fields.String()
    addressbook_name  = fields.String()


class ContactImportResponseSchema(ApiBaseResponse):
    """Response schema for an import call."""

    data = fields.Nested(ContactImportResultDataSchema, allow_none=True)


class ContactImportUploadSchema(Schema):
    """Multipart file upload schema for the import endpoint.

    Declares the ``file`` part so Swagger renders an upload widget. The actual binary read happens in
    the view since Marshmallow does not deserialize the FileStorage object.
    """

    file = fields.Raw(
        required=True,
        metadata={"type": "string", "format": "binary",
                  "description": "The JSON (.json), vCard (.vcf) or LDIF (.ldif) file to import."},
    )
