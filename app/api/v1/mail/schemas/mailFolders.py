from marshmallow import Schema, fields
from app.utils.api.ApiResponse import ApiBaseResponse

class FolderSchema(Schema):
    """
    Schema representing a mail folder.
    """
    name = fields.String(required=True)

class FolderListResponseSchema(ApiBaseResponse):
    """
    Schema representing a response containing a list of mail folders.
    """
    data = fields.Dict(required=True, metadata={
        'description': 'Contains the folders list',
        'example': {'folders': []}
    })
