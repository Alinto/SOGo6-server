"""Nested schemas describing the structure of contact sub-objects (vCard properties).

They replace the opaque ``fields.Dict()`` so the OpenAPI documentation tells the API user
exactly what each sub-object contains, with ``required`` on the mandatory fields. Same style as
the calendar and mail API schemas. Unknown keys are rejected (Marshmallow default).
"""
from __future__ import annotations

from marshmallow import Schema, fields


class CardEmailSchema(Schema):
    """vCard EMAIL property (RFC 6350 §6.4.2)."""

    value = fields.String(required=True, metadata={"description": "Email address.", "example": "john@example.com"})
    types = fields.List(fields.String(), load_default=list,
                        metadata={"description": "TYPE parameter values (e.g. work, home)."})
    pref  = fields.Integer(allow_none=True, metadata={"description": "PREF parameter (1 = most preferred)."})


class CardPhoneSchema(Schema):
    """vCard TEL property (RFC 6350 §6.4.1)."""

    number = fields.String(required=True, metadata={"description": "Phone number.", "example": "+33123456789"})
    types  = fields.List(fields.String(), load_default=list,
                         metadata={"description": "TYPE parameter values (e.g. cell, work)."})
    pref   = fields.Integer(allow_none=True, metadata={"description": "PREF parameter (1 = most preferred)."})


class CardAddressSchema(Schema):
    """vCard ADR property (RFC 6350 §6.3.1)."""

    po_box      = fields.String(allow_none=True)
    extended    = fields.String(allow_none=True)
    street      = fields.String(allow_none=True)
    locality    = fields.String(allow_none=True, metadata={"description": "City."})
    region      = fields.String(allow_none=True, metadata={"description": "State or province."})
    postal_code = fields.String(allow_none=True)
    country     = fields.String(allow_none=True)
    types       = fields.List(fields.String(), load_default=list)
    pref        = fields.Integer(allow_none=True)


class CardUrlSchema(Schema):
    """vCard URL property (RFC 6350 §6.7.8)."""

    value = fields.String(required=True, metadata={"example": "https://example.com"})
    type  = fields.String(allow_none=True, metadata={"description": "TYPE parameter (e.g. work, home)."})


class CardImppSchema(Schema):
    """vCard IMPP property (RFC 6350 §6.4.3) - instant messaging address."""

    uri  = fields.String(required=True, metadata={"example": "xmpp:john@example.com"})
    type = fields.String(allow_none=True)


class AddressBookRefSchema(Schema):
    """Lightweight reference to the address book a suggestion comes from."""

    key  = fields.String(allow_none=True)
    name = fields.String(allow_none=True)
