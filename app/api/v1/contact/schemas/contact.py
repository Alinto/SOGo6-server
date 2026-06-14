from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate

from app.api.v1.contact.schemas.components import AddressSchema, EmailSchema, ImppSchema, PhoneSchema, UrlSchema
from app.module.contact.model.enums.CardKind import CardKind
from app.utils.api.ApiBaseResponse import ApiBaseResponse

_KIND_VALUES = [k.value for k in CardKind]


def validate_search(value: str | None) -> None:
    """Reject a too-short search query (less than 2 non-whitespace characters)."""
    if value is not None and len(value.strip()) < 2:
        raise ValidationError("Search query must contain at least 2 non-whitespace characters.")


class ContactWriteSchema(Schema):
    """Shared writable fields for creating or patching a contact (all optional).

    vCard requires a formatted name (FN); when display_name is omitted the server derives it from
    the structured name, organization or nickname. Identity (uid, key) and server-managed fields
    (rev, timestamps) are never accepted from the request body.
    """

    display_name  = fields.String(allow_none=True, metadata={"description": "Formatted name (vCard FN).", "example": "John Doe"})
    first_name    = fields.String(allow_none=True)
    last_name     = fields.String(allow_none=True)
    middle_name   = fields.String(allow_none=True)
    prefix        = fields.String(allow_none=True, metadata={"description": "Honorific prefix (e.g. Dr)."})
    suffix        = fields.String(allow_none=True, metadata={"description": "Honorific suffix (e.g. Jr)."})
    nickname      = fields.String(allow_none=True)
    kind          = fields.String(load_default=CardKind.INDIVIDUAL.value, validate=validate.OneOf(_KIND_VALUES))
    organization  = fields.String(allow_none=True)
    department    = fields.String(allow_none=True)
    job_title     = fields.String(allow_none=True)
    role          = fields.String(allow_none=True)
    emails        = fields.List(fields.Nested(EmailSchema), load_default=list)
    phones        = fields.List(fields.Nested(PhoneSchema), load_default=list)
    addresses     = fields.List(fields.Nested(AddressSchema), load_default=list)
    urls          = fields.List(fields.Nested(UrlSchema), load_default=list)
    impp          = fields.List(fields.Nested(ImppSchema), load_default=list)
    photos        = fields.List(fields.String(), load_default=list, metadata={"description": "Photo URIs."})
    categories    = fields.List(fields.String(), load_default=list)
    birthday      = fields.String(allow_none=True, metadata={"description": "ISO date (YYYY-MM-DD)."})
    anniversary   = fields.String(allow_none=True, metadata={"description": "ISO date (YYYY-MM-DD)."})
    geo           = fields.String(allow_none=True, metadata={"description": "geo:lat,lon."})
    note          = fields.String(allow_none=True)
    public_key    = fields.String(allow_none=True, metadata={"description": "Public key URI."})
    sound         = fields.String(allow_none=True)
    timezone      = fields.String(allow_none=True)
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String(), load_default=dict)


class ContactCreateSchema(ContactWriteSchema):
    """Request body for creating a contact."""


class ContactPatchSchema(ContactWriteSchema):
    """Request body for patching a contact (only the provided fields are modified)."""


class ContactSchema(Schema):
    """Representation of a contact in API responses (vCard, RFC 6350)."""

    key            = fields.String()
    addressbook_key = fields.String(allow_none=True)
    uid            = fields.String(allow_none=True)
    version        = fields.String()
    kind           = fields.String()
    display_name   = fields.String(allow_none=True)
    first_name     = fields.String(allow_none=True)
    last_name      = fields.String(allow_none=True)
    middle_name    = fields.String(allow_none=True)
    prefix         = fields.String(allow_none=True)
    suffix         = fields.String(allow_none=True)
    nickname       = fields.String(allow_none=True)
    organization   = fields.String(allow_none=True)
    department     = fields.String(allow_none=True)
    job_title      = fields.String(allow_none=True)
    role           = fields.String(allow_none=True)
    emails         = fields.List(fields.Nested(EmailSchema))
    phones         = fields.List(fields.Nested(PhoneSchema))
    addresses      = fields.List(fields.Nested(AddressSchema))
    urls           = fields.List(fields.Nested(UrlSchema))
    impp           = fields.List(fields.Nested(ImppSchema))
    photos         = fields.List(fields.String())
    categories     = fields.List(fields.String())
    birthday       = fields.String(allow_none=True)
    anniversary    = fields.String(allow_none=True)
    geo            = fields.String(allow_none=True)
    note           = fields.String(allow_none=True)
    public_key     = fields.String(allow_none=True)
    sound          = fields.String(allow_none=True)
    timezone       = fields.String(allow_none=True)
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String())
    rev            = fields.String(allow_none=True)
    created_at     = fields.String(allow_none=True)
    updated_at     = fields.String(allow_none=True)


class ContactSearchQueryArgsSchema(Schema):
    """Query string for the contact list endpoints (search only; pagination is handled separately)."""

    search = fields.String(load_default=None, allow_none=True, validate=validate_search,
                           metadata={"description": "Full-text query (min 2 non-whitespace characters)."})


class ContactListDataSchema(Schema):
    """Data payload for the contact list response. The total count is in the X-Pagination header."""

    contacts = fields.List(fields.Nested(ContactSchema))


class ContactListResponseSchema(ApiBaseResponse):
    """Response schema for a paginated list of contacts."""

    data = fields.Nested(ContactListDataSchema, allow_none=True)


class ContactResponseSchema(ApiBaseResponse):
    """Response schema for a single contact."""

    data = fields.Nested(ContactSchema, allow_none=True)
