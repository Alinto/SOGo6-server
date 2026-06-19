from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate

from app.api.v1.contact.schemas.components import (
    AddressBookRefSchema,
    ContactAddressSchema,
    ContactEmailSchema,
    ContactImppSchema,
    ContactPhoneSchema,
    ContactUrlSchema,
)
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
    emails        = fields.List(fields.Nested(ContactEmailSchema), load_default=list)
    phones        = fields.List(fields.Nested(ContactPhoneSchema), load_default=list)
    addresses     = fields.List(fields.Nested(ContactAddressSchema), load_default=list)
    urls          = fields.List(fields.Nested(ContactUrlSchema), load_default=list)
    impp          = fields.List(fields.Nested(ContactImppSchema), load_default=list)
    photos        = fields.List(fields.String(), load_default=list, metadata={"description": "Photo URIs."})
    categories    = fields.List(fields.String(), load_default=list)
    birthday      = fields.String(allow_none=True, metadata={"description": "Date YYYY-MM-DD, or year-less --MM-DD."})
    anniversary   = fields.String(allow_none=True, metadata={"description": "Date YYYY-MM-DD, or year-less --MM-DD."})
    geo           = fields.String(allow_none=True, metadata={"description": "geo:lat,lon."})
    note          = fields.String(allow_none=True)
    public_key    = fields.String(allow_none=True, metadata={"description": "Public key URI."})
    sound         = fields.String(allow_none=True)
    timezone      = fields.String(allow_none=True)
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String(), load_default=dict)


class ContactCreateSchema(ContactWriteSchema):
    """Request body for creating a contact."""


class ContactPatchSchema(ContactWriteSchema):
    """Request body for patching a contact (only the provided fields are modified).

    Unlike the create schema, the multi-valued fields carry NO load_default: an absent field must
    stay absent in the loaded body so the partial merge leaves the stored value untouched. With a
    load_default Marshmallow would inject an empty list/dict for an omitted field and the merge would
    wipe the existing emails/phones/etc.
    """

    kind             = fields.String(validate=validate.OneOf(_KIND_VALUES))
    emails           = fields.List(fields.Nested(ContactEmailSchema))
    phones           = fields.List(fields.Nested(ContactPhoneSchema))
    addresses        = fields.List(fields.Nested(ContactAddressSchema))
    urls             = fields.List(fields.Nested(ContactUrlSchema))
    impp             = fields.List(fields.Nested(ContactImppSchema))
    photos           = fields.List(fields.String())
    categories       = fields.List(fields.String())
    extra_properties = fields.Dict(keys=fields.String(), values=fields.String())


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
    emails         = fields.List(fields.Nested(ContactEmailSchema))
    phones         = fields.List(fields.Nested(ContactPhoneSchema))
    addresses      = fields.List(fields.Nested(ContactAddressSchema))
    urls           = fields.List(fields.Nested(ContactUrlSchema))
    impp           = fields.List(fields.Nested(ContactImppSchema))
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
    import_format  = fields.String(metadata={"description": "Format the contact was imported from (read-only)."})
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


class ContactAutocompleteQueryArgsSchema(Schema):
    """Query string for the recipient autocompletion endpoint."""

    q = fields.String(required=True, metadata={"description": "Partial name or email to autocomplete."})


class SuggestionMemberSchema(Schema):
    """A resolved member of a distribution-list suggestion (recipient name + email)."""

    contact_key = fields.String(allow_none=True)
    name        = fields.String(allow_none=True)
    email       = fields.String(allow_none=True)


class ContactSuggestionSchema(Schema):
    """A single recipient suggestion: a contact email or a distribution list.

    type discriminates the two: a "contact" carries an email (one suggestion per address), a "list"
    carries list_key, member_count and the full list of its members (each name + email) instead of
    an email. contact_key/list_key and address_book are nullable - future sources (the directory,
    collected mail addresses) may not map to a stored object or a real address book.
    """

    type         = fields.String(metadata={"description": "Suggestion kind: 'contact' or 'list'."})
    name         = fields.String(allow_none=True)
    email        = fields.String(allow_none=True)
    contact_key  = fields.String(allow_none=True)
    list_key     = fields.String(allow_none=True)
    member_count = fields.Integer(allow_none=True, metadata={"description": "Number of members (lists only)."})
    members      = fields.List(fields.Nested(SuggestionMemberSchema), allow_none=True,
                               metadata={"description": "Resolved members of the list (lists only)."})
    address_book = fields.Nested(AddressBookRefSchema, allow_none=True)


class ContactAutocompleteDataSchema(Schema):
    """Data payload for the autocompletion response."""

    suggestions = fields.List(fields.Nested(ContactSuggestionSchema))


class ContactAutocompleteResponseSchema(ApiBaseResponse):
    """Response schema for recipient autocompletion."""

    data = fields.Nested(ContactAutocompleteDataSchema, allow_none=True)
