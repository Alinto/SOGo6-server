"""Nested schemas describing the structure of contact sub-objects (vCard properties).

They replace the opaque ``fields.Dict()`` so the OpenAPI documentation tells the API user
exactly what each sub-object contains, with ``required`` on the mandatory fields. Same style as
the calendar and mail API schemas. Unknown keys are rejected (Marshmallow default).
"""
from __future__ import annotations

from marshmallow import Schema, fields


class EmailSchema(Schema):
    """vCard EMAIL property (RFC 6350 6.4.2)."""

    value = fields.String(required=True, metadata={"description": "Email address.", "example": "john@example.com"})
    types = fields.List(fields.String(), load_default=list,
                        metadata={"description": "TYPE parameter values (e.g. work, home)."})
    pref  = fields.Integer(allow_none=True, metadata={"description": "PREF parameter (1 = most preferred)."})


class PhoneSchema(Schema):
    """vCard TEL property (RFC 6350 6.4.1)."""

    number = fields.String(required=True, metadata={"description": "Phone number.", "example": "+33123456789"})
    types  = fields.List(fields.String(), load_default=list,
                         metadata={"description": "TYPE parameter values (e.g. cell, work)."})
    pref   = fields.Integer(allow_none=True, metadata={"description": "PREF parameter (1 = most preferred)."})


class AddressSchema(Schema):
    """vCard ADR property (RFC 6350 6.3.1)."""

    po_box      = fields.String(allow_none=True)
    extended    = fields.String(allow_none=True)
    street      = fields.String(allow_none=True)
    locality    = fields.String(allow_none=True, metadata={"description": "City."})
    region      = fields.String(allow_none=True, metadata={"description": "State or province."})
    postal_code = fields.String(allow_none=True)
    country     = fields.String(allow_none=True)
    types       = fields.List(fields.String(), load_default=list)
    pref        = fields.Integer(allow_none=True)


class UrlSchema(Schema):
    """vCard URL property (RFC 6350 6.7.8)."""

    value = fields.String(required=True, metadata={"example": "https://example.com"})
    type  = fields.String(allow_none=True, metadata={"description": "TYPE parameter (e.g. work, home)."})


class ImppSchema(Schema):
    """vCard IMPP property (RFC 6350 6.4.3) - instant messaging address."""

    uri  = fields.String(required=True, metadata={"example": "xmpp:john@example.com"})
    type = fields.String(allow_none=True)
