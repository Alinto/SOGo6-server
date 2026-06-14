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


class AddressBookSchema(Schema):
    """Representation of an address book in API responses."""

    key         = fields.String()
    name        = fields.String()
    description = fields.String(allow_none=True)
    is_default  = fields.Boolean()
    source_type = fields.String()
    ctag        = fields.Integer(metadata={"description": "CardDAV change tag, bumped on every contact mutation."})


class AddressBookListDataSchema(Schema):
    """Data payload for the address book list response."""

    addressbooks = fields.List(fields.Nested(AddressBookSchema))
    total_count  = fields.Integer()


class AddressBookListResponseSchema(ApiBaseResponse):
    """Response schema for a list of address books."""

    data = fields.Nested(AddressBookListDataSchema, allow_none=True)


class AddressBookResponseSchema(ApiBaseResponse):
    """Response schema for a single address book."""

    data = fields.Nested(AddressBookSchema, allow_none=True)
