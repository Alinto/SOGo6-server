from marshmallow import Schema, fields

class ApiBaseResponse(Schema):
    """
    Basic response for api
    """

    status = fields.Boolean(required=True)
    data = fields.Dict(required=True)
    errors = fields.String(allow_none=True)