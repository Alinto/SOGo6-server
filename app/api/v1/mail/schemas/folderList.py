from marshmallow import Schema, fields
from app.utils.api.ApiResponse import ApiBaseResponse

class FolderListResponseSchema(ApiBaseResponse):
    """
    Schema representing a response containing a list of mail folders.
    """
    data = fields.List(
        fields.Dict(keys=fields.String(), values=fields.Raw()),
        required=True,
        metadata={
            'description': 'List of mail folders',
            'example': [
                {'name': 'Trash'},
                {'name': 'INBOX'}
            ]
        }
    )  # type: ignore[assignment]
