from marshmallow import Schema, fields
from app.utils.api.ApiBaseResponse import ApiBaseResponse

class FolderCreateSchema(Schema):
    """
    Schema for creating a new mail folder.
    """
    name = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder creation.

        :return: Example folder creation payload.
        :rtype: dict
        """
        return {
            "name": "NewFolder"
        }


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


class FolderSchema(Schema):
    """
    Schema representing a mail folder.
    """
    name = fields.String(required=True)


class FolderUpdateSchema(Schema):
    """
    Schema for updating a mail folder.
    """
    name = fields.String(required=False, allow_none=True, metadata={'description': 'New folder name'})
    subscribed = fields.Integer(required=False, allow_none=True, metadata={'description': 'Subscription status (0 or 1)'})
    type = fields.String(required=False, allow_none=True, metadata={'description': 'Folder type (folder, junk, templates, etc.)'})

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder update.

        :return: Example folder update payload.
        :rtype: dict
        """
        return {
            "name": "NewFolder_renamed",
            "subscribed": 1,
            "type": "folder"
        }


class FolderPurgeSchema(Schema):
    """
    Schema for purging mails in a folder.
    """
    applyToSubfolders = fields.Boolean()
    permanentlyDelete = fields.Boolean()
    date = fields.String()

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder purge.

        :return: Example folder purge payload.
        :rtype: dict
        """
        return {
            "applyToSubfolders": True,
            "permanentlyDelete": True,
            "date": "2025-12-11"
        }


class FolderShareRightsSchema(Schema):
    """
    Schema for folder sharing rights.
    """
    userCanEraseMails = fields.Integer(required=False, allow_none=True)
    userCanExpungeFolder = fields.Integer(required=False, allow_none=True)
    userCanInsertMails = fields.Integer(required=False, allow_none=True)
    userIsAdministrator = fields.Integer(required=False, allow_none=True)
    userCanWriteMails = fields.Integer(required=False, allow_none=True)
    userCanMarkMailsRead = fields.Integer(required=False, allow_none=True)
    userCanViewFolder = fields.Integer(required=False, allow_none=True)
    userCanCreateSubfolders = fields.Integer(required=False, allow_none=True)
    userCanPostMails = fields.Integer(required=False, allow_none=True)
    userCanReadMails = fields.Integer(required=False, allow_none=True)
    userCanRemoveFolder = fields.Integer(required=False, allow_none=True)


class FolderShareSchema(Schema):
    """
    Schema for a user entry in folder sharing.
    Use with many=True to validate a list of users.
    """
    isGroup = fields.Integer(required=False, allow_none=True)
    c_email = fields.String(required=False, allow_none=True)
    cn = fields.String(required=False, allow_none=True)
    uid = fields.String(required=True)
    userClass = fields.String(required=False, allow_none=True)
    rights = fields.Nested(FolderShareRightsSchema, required=False, allow_none=True)

    @classmethod
    def example(cls) -> list:
        """
        Example data for folder sharing.

        :return: Example folder share payload (a list).
        :rtype: list
        """
        return[
            {
                "isGroup": 0,
                "c_email": "tkeriven@snapshot.alinto.org",
                "cn": "tkeriven",
                "uid": "tkeriven@snapshot.alinto.org",
                "userClass": "normal-user",
                "rights": {
                "userCanInsertMails": 1,
                "userCanMarkMailsRead": 1,
                "userCanPostMails": 1,
                "userCanReadMails": 1,
                "userCanRemoveFolder": 1,
                "userCanViewFolder": 1,
                "userCanWriteMails": 1,
                "userIsAdministrator": 1
                }
            },
            {
                "isGroup": 0,
                "c_email": "jnadal@snapshot.alinto.org",
                "cn": "jnadal",
                "uid": "jnadal@snapshot.alinto.org",
                "userClass": "normal-user",
                "rights": {
                "userCanInsertMails": 1,
                "userCanMarkMailsRead": 1,
                "userCanPostMails": 1,
                "userCanReadMails": 1,
                "userCanRemoveFolder": 1,
                "userCanViewFolder": 1,
                "userCanWriteMails": 1,
                "userIsAdministrator": 1
                }
            }
    ]
