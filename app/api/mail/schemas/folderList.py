from marshmallow import Schema, fields

class FolderSchema(Schema):
    name = fields.String(required=True)

class FolderListResponseSchema(Schema):
    status = fields.Boolean(required=True)
    folders = fields.List(fields.Nested(FolderSchema), required=True)
    errors = fields.String(allow_none=True)