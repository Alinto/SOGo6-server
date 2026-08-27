from typing import Any

from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app.utils.api.ApiBaseResponse import ApiBaseResponse
# The correspondence table lives in app.factory.share.shareMailFolder - shared with ModuleMail's
# IMAP ACL calls (see ClientImap.set_acl_raw/get_acl_raw) - and re-imported here for schema use.
from app.factory.share.shareMailFolder import FOLDER_SHARE_PERMISSION_CODES, FOLDER_PERMISSION_CODE_TO_RIGHT


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


class FolderShareRightsInputSchema(Schema):
    """
    Advanced permission rights (one flag per IMAP ACL code) for the folder sharing request body.

    Every field is a 0/1 flag and optional: only pass the rights you want to state explicitly.
    See ``FOLDER_PERMISSION_CODE_TO_RIGHT`` for the IMAP code each field corresponds to.
    """
    user_can_view_folder = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Voir le dossier (l)"})
    user_can_read_mails = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Lire les mails (r)"})
    user_can_mark_mails_read = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Marquer comme lu/non lu (s)"})
    user_can_write_mails = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Modifier les indicateurs des mails (w)"})
    user_can_insert_mails = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Insérer, copier des mails (i)"})
    user_can_post_mails = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Envoyer des mails (p)"})
    user_can_create_subfolders = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Créer des sous-dossiers (k)"})
    user_can_remove_folder = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Supprimer le dossier (x)"})
    user_can_erase_mails = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Effacer les mails (t)"})
    user_can_expunge_folder = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Purger le dossier (e)"})
    user_is_administrator = fields.Integer(validate=validate.OneOf([0, 1]), metadata={"description": "Administrer les droits du dossier (a)"})


class FolderShareEntrySchema(Schema):
    """
    Base schema for a user (or "anyone") entry in a mail folder sharing request.

    Rights can be expressed two ways, and at least one of them must be provided:

    - ``permissions``: a simplified list of IMAP ACL codes to grant (``l r s w i p k x t e a``).
      Any code not listed is considered not granted.
    - ``rights``: an advanced object with one explicit 0/1 flag per right
      (see :class:`FolderShareRightsInputSchema`).

    If both ``permissions`` and ``rights`` are provided, they must agree: each code in
    ``permissions`` must match its corresponding ``rights`` flag (see
    ``FOLDER_PERMISSION_CODE_TO_RIGHT`` for the code <-> flag mapping). Otherwise the API
    answers ``400 S001103`` (see ``ERROR_SHARE_PERMISSIONS_RIGHTS_MISMATCH`` in
    ``app/utils/errors.py``).

    ``c_email`` and ``uid`` are required unless ``user_class`` is ``"anyone"``, in which case
    they are ignored (the share applies to any authenticated user, not a specific one).
    """
    c_email = fields.String(required=False, allow_none=True, metadata={"description": "User email address", "example": "a@a.fr"})
    uid = fields.String(required=False, allow_none=True, metadata={"description": "User UID", "example": "a@a.fr"})
    user_class = fields.String(
        required=True,
        validate=validate.OneOf(["user", "anyone"]),
        metadata={"description": "'user' for a specific user (needs c_email/uid), 'anyone' for every authenticated user"}
    )
    permissions = fields.List(
        fields.String(validate=validate.OneOf(FOLDER_SHARE_PERMISSION_CODES)),
        required=False,
        metadata={"description": "Simplified list of IMAP ACL codes to grant: l, r, s, w, i, p, k, x, t, e, a"}
    )
    rights = fields.Nested(
        FolderShareRightsInputSchema,
        required=False,
        metadata={"description": "Advanced per-right 0/1 flags, cross-checked against 'permissions' if both are given"}
    )
    do_subfolders = fields.Boolean(
        load_default=False, dump_default=False,
        metadata={"description": "Also apply these rights to all subfolders"}
    )

    @validates_schema
    def validate_user_identity(self, data: dict[str, Any], **kwargs: Any) -> None:  # pylint: disable=unused-argument
        """Require c_email and uid unless user_class is 'anyone'."""
        if data.get("user_class") == "anyone":
            return
        errors: dict[str, list[str]] = {}
        if not data.get("c_email"):
            errors["c_email"] = ["Missing data for required field."]
        if not data.get("uid"):
            errors["uid"] = ["Missing data for required field."]
        if errors:
            raise ValidationError(errors)

    @validates_schema
    def validate_permissions_or_rights(self, data: dict[str, Any], **kwargs: Any) -> None:  # pylint: disable=unused-argument
        """Require at least one of 'permissions' or 'rights'."""
        if not data.get("permissions") and not data.get("rights"):
            raise ValidationError(
                "At least one of 'permissions' or 'rights' must be provided.",
                field_name="_schema"
            )


class FolderSharePatchSchema(FolderShareEntrySchema):
    """Request body item for PATCH /mailboxes/{account_id}/folders/{folder_name}/share.

    Partially updates the sharing rights of the specified users: only the users listed in the
    request body are modified, other existing shares are left untouched.
    The endpoint expects a JSON list of these objects (use with ``many=True``).
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "uid": "a@a.fr",
                "c_email": "a@a.fr",
                "user_class": "user",
                "permissions": ["l", "r"],
                "do_subfolders": False
            }
        ]


class FolderSharePutSchema(FolderShareEntrySchema):
    """Request body item for PUT /mailboxes/{account_id}/folders/{folder_name}/share.

    Replaces all sharing rights on the folder: existing shares are entirely replaced by the
    users listed in the request body.
    The endpoint expects a JSON list of these objects (use with ``many=True``).
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "user_class": "anyone",
                "permissions": ["l", "r", "s", "w", "i", "p", "t", "e", "a"],
                "do_subfolders": True
            },
            {
                "c_email": "a@a.fr",
                "uid": "a@a.fr",
                "user_class": "user",
                "permissions": ["l", "r"],
                "do_subfolders": False
            }
        ]


class FolderSharePostSchema(FolderShareEntrySchema):
    """Request body item for POST /mailboxes/{account_id}/folders/{folder_name}/share.

    Grants (or creates) sharing rights for the specified users, in addition to any existing share.
    The endpoint expects a JSON list of these objects (use with ``many=True``).
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "sogo-tests1@example.org",
                "uid": "sogo-tests1@example.org",
                "user_class": "user",
                "rights": {
                    "user_can_insert_mails": 1,
                    "user_can_mark_mails_read": 1,
                    "user_can_post_mails": 1,
                    "user_can_read_mails": 1,
                    "user_can_remove_folder": 1,
                    "user_can_view_folder": 1,
                    "user_can_write_mails": 1,
                    "user_is_administrator": 1
                },
                "permissions": ["l", "r", "s", "w", "i", "p", "x", "a"]
            },
            {
                "user_class": "anyone",
                "permissions": ["l", "r"],
                "do_subfolders": False
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
                    "sogo-tests1@example.org": {
                        "user_class": "user",
                        "c_email": "sogo-tests1@example.org",
                        "uid": "sogo-tests1@example.org",
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
                        "uid": "anyone",
                        "rights": {
                            "userCanViewFolder": 1,
                            "userCanReadMails": 1
                        }
                    }
                }
            }
        }
