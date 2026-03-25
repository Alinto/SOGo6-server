from marshmallow import Schema, fields
from app.utils.api.ApiBaseResponse import ApiBaseResponse


class FolderCreateSchema(Schema):
    """
    Schema for creating a new mail folder.
    """
    parent = fields.String(required=True)
    name = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder creation.

        :return: Example folder creation payload.
        :rtype: dict
        """
        return {
            "name": "NewFolder",
            "parent": ""
        }


class FolderUpdateSchema(Schema):
    """
    Schema for updating a mail folder.
    """
    name = fields.String()
    subscribed = fields.Integer()
    type = fields.String()

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
    do_subfolders = fields.Boolean(load_default=True, dump_default=True)
    permanently_delete = fields.Boolean(load_default=False, dump_default=False)
    date = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder purge.

        :return: Example folder purge payload.
        :rtype: dict
        """
        return {
            "do_subfolders": True,
            "permanently_delete": True,
            "date": "2025-12-11"
        }


class FolderShareRightsSchema(Schema):
    """
    Schema for folder sharing rights.
    """
    userCanEraseMails = fields.Integer()
    userCanExpungeFolder = fields.Integer()
    userCanInsertMails = fields.Integer()
    userIsAdministrator = fields.Integer()
    userCanWriteMails = fields.Integer()
    userCanMarkMailsRead = fields.Integer()
    userCanViewFolder = fields.Integer()
    userCanCreateSubfolders = fields.Integer()
    userCanPostMails = fields.Integer()
    userCanReadMails = fields.Integer()
    userCanRemoveFolder = fields.Integer()


class FolderShareSchema(Schema):
    """
    Schema for a user entry in folder sharing.
    Use with many=True to validate a list of users.
    """
    is_group = fields.Integer()
    c_email = fields.String(required=True)
    cn = fields.String()
    uid = fields.String(required=True)
    user_class = fields.String()
    rights = fields.Nested(FolderShareRightsSchema, )

    @classmethod
    def example(cls) -> list:
        """
        Example data for folder sharing.

        :return: Example folder share payload (a list).
        :rtype: list
        """
        return [
            {
                "c_email": "tkeriven@snapshot.alinto.org",
                "cn": "tkeriven",
                "uid": "tkeriven@snapshot.alinto.org",
                "user_class": "user",
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
                "c_email": "jnadal@snapshot.alinto.org",
                "cn": "jnadal",
                "uid": "jnadal@snapshot.alinto.org",
                "user_class": "user",
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


class FolderListResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders response
    """
    data = fields.List(fields.Dict(), required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder list.
        
        :return: Example folder list response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [
                {
                    "name": "INBOX",
                    "path": "INBOX",
                    "subscribed": 1,
                    "type": "inbox",
                    "unseen_count": 5,
                    "message_count": 42,
                    "children": []
                },
                {
                    "name": "Trash",
                    "path": "Trash",
                    "subscribed": 0,
                    "type": "trash",
                    "unseen_count": 0,
                    "message_count": 50,
                    "children": []
                },
                {
                    "name": "piou",
                    "path": "piou",
                    "subscribed": 0,
                    "type": "folder",
                    "unseen_count": 0,
                    "message_count": 50,
                    "children": [
                        {
                            "name": "test",
                            "path": "piou/test",
                            "subscribed": 0,
                            "type": "folder",
                            "unseen_count": 0,
                            "message_count": 10,
                            "children": []
                        }
                    ]
                }
            ]
        }


class FolderCreateResponseSchema(ApiBaseResponse):
    """
    Schema for POST /mailboxes/<account_id>/folders response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder creation.
        
        :return: Example folder creation response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "name": "NewFolder"
            }
        }


class FolderDetailsResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name> response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder details.
        
        :return: Example folder details response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "name": "INBOX",
                "path": "INBOX",
                "subscribed": 1,
                "type": "folder",
                "unseen_count": 5,
                "message_count": 42,
                "children": []
            }
        }


class FolderUpdateResponseSchema(ApiBaseResponse):
    """
    Schema for PATCH /mailboxes/<account_id>/folders/<path:folder_name> response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder update.
        
        :return: Example folder update response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "name": "RenamedFolder",
                "path": "RenamedFolder",
                "subscribed": 1,
                "type": "folder",
                "unseen_count": 0,
                "message_count": 10,
                "children": []
            }
        }

class FolderExpungeSchema(Schema):
    """
    Schema for purging mails in a folder.
    """
    do_subfolders = fields.Boolean(load_default=True, dump_default=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder purge.

        :return: Example folder purge payload.
        :rtype: dict
        """
        return {
            "do_subfolders": True,
        }

class FolderExpungeResponseSchema(ApiBaseResponse):
    """
    Schema for POST /mailboxes/<account_id>/folders/<path:folder_name>/expunge response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder expunge.
        
        :return: Example folder expunge response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "mail_deleted": 15
            }
        }


class FolderPurgeResponseSchema(ApiBaseResponse):
    """
    Schema for POST /mailboxes/<account_id>/folders/<path:folder_name>/purge response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder purge.
        
        :return: Example folder purge response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "mails_deleted": 23
            }
        }


class FolderShareResponseSchema(ApiBaseResponse):
    """
    Schema for GET/POST /mailboxes/<account_id>/folders/<path:folder_name>/share response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for folder share.
        
        :return: Example folder share response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "users": {
                    "tkeriven@snapshot.alinto.org": {
                        "user_class": "user",
                        "c_email": "tkeriven@snapshot.alinto.org",
                        "cn": "tkeriven",
                        "uid": "tkeriven@snapshot.alinto.org",
                        "rights": {
                            "userCanEraseMails": 1,
                            "userCanExpungeFolder": 1,
                            "userCanInsertMails": 1,
                            "userIsAdministrator": 1,
                            "userCanWriteMails": 1,
                            "userCanMarkMailsRead": 1,
                            "userCanViewFolder": 1,
                            "userCanCreateSubfolders": 1,
                            "userCanPostMails": 1,
                            "userCanReadMails": 1,
                            "userCanRemoveFolder": 1
                        }
                    },
                    "anyone": {
                        "user_class": "anyone",
                        "cn": "Tout utilisateur identifié",
                        "uid": "anyone",
                        "rights": {
                            "userCanViewFolder": 1,
                            "userCanReadMails": 1
                        }
                    }
                }
            }
        }
