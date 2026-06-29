from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class ListCreateSchema(Schema):
    """Request body for creating a distribution list."""

    name        = fields.String(required=True, validate=validate.Length(min=1, max=255),
                                metadata={"example": "Project team"})
    description = fields.String(load_default=None, allow_none=True,
                                metadata={"example": "Everyone working on the project"})
    members     = fields.List(fields.String(), load_default=list,
                              metadata={"description": "Member contact keys (references)."})


class ListPatchSchema(Schema):
    """Request body for patching a distribution list (only the provided fields are modified)."""

    name        = fields.String(validate=validate.Length(min=1, max=255), metadata={"example": "Core team"})
    description = fields.String(allow_none=True)
    members     = fields.List(fields.String(),
                              metadata={"description": "Full replacement of the member contact keys."})


class DistributionListSchema(Schema):
    """Representation of a distribution list in API responses (vCard KIND:group, RFC 6350)."""

    key          = fields.String()
    uid          = fields.String(allow_none=True)
    name         = fields.String()
    description  = fields.String(allow_none=True)
    members      = fields.List(fields.String(), metadata={"description": "Member contact keys."})
    member_count = fields.Integer()
    created_at   = fields.String(allow_none=True)
    updated_at   = fields.String(allow_none=True)


class ListSearchQueryArgsSchema(Schema):
    """Query string for the list collection endpoint (name filter; pagination is handled separately)."""

    search = fields.String(load_default=None, allow_none=True,
                           metadata={"description": "Case-insensitive name filter."})


class ListCollectionDataSchema(Schema):
    """Data payload for the list collection response. The total count is in the X-Pagination header."""

    lists = fields.List(fields.Nested(DistributionListSchema))


class ListCollectionResponseSchema(ApiBaseResponse):
    """Response schema for a paginated collection of distribution lists."""

    data = fields.Nested(ListCollectionDataSchema, allow_none=True)


class ListResponseSchema(ApiBaseResponse):
    """Response schema for a single distribution list."""

    data = fields.Nested(DistributionListSchema, allow_none=True)
