from marshmallow import Schema, fields, validate
from app.utils.api.ApiBaseResponse import ApiBaseResponse


class MailDeleteSchema(Schema):
    """
    Schema for deleting multiple emails.
    """
    mail_uids = fields.List(fields.Integer(), required=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for mail deletion.
        
        :return: Example mail deletion payload
        :rtype: dict
        """
        return {
            "mail_uids": [1, 2, 3, 4, 5]
        }


class MailMoveSchema(Schema):
    """
    Schema for moving multiple emails to another folder.
    """
    mail_uids = fields.List(fields.Integer(), required=True)
    to_folder_name = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for moving mails.
        
        :return: Example mail move payload
        :rtype: dict
        """
        return {
            "mail_uids": [1, 2, 3],
            "to_folder_name": "Archive"
        }


class MailFolderQueryArgsSchema(Schema):
    """
    Schema for query parameters when deleting emails in a folder.
    """
    before_date = fields.String(required=False, allow_none=True)

class MailActionSchema(Schema):
    """
    Schema for performing actions on a mail.
    """
    action = fields.String(
        required=True,
        validate=validate.OneOf(['tag', 'untag', 'move', 'spam', 'ham', 'copy', 'delete'])
    )
    data = fields.Raw(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for mail action.
        
        :return: Example mail action payload
        :rtype: dict
        """
        return {
            "action": "tag",
            "data": ["important", "work"]
        }


class MailBatchActionSchema(Schema):
    """
    Schema for performing an action on multiple mails at once.
    """
    uids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    action = fields.String(
        required=True,
        validate=validate.OneOf(['tag', 'untag', 'move', 'spam', 'ham', 'copy', 'delete'])
    )
    data = fields.Raw(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for mail batch action.

        :return: Example mail batch action payload
        :rtype: dict
        """
        return {
            "uids": [12345, 12346, 12350],
            "action": "tag",
            "data": ["important", "work"]
        }


class MailBatchActionResponseSchema(ApiBaseResponse):
    """
    Schema for the mail batch action response.
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for mail batch action.

        :return: Example mail batch action response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "action": "tag",
                "mail_uids": [12345, 12346, 12350],
                "tags_added": ["important", "work"]
            }
        }


class MailDownloadSchema(Schema):
    """
    Schema for downloading a mail as .eml or .zip.
    """
    format = fields.String(
        required=True,
        validate=validate.OneOf(['eml', 'zip'])
    )

    @classmethod
    def example(cls) -> dict:
        """Example data for mail download.
        
        :return: Example mail download payload
        :rtype: dict
        """
        return {
            "format": "eml"
        }


class MailDetailResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid> response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for mail detail.
        
        :return: Example mail detail response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "uid": "42",
                "size": 12543,
                "seen": False,
                "flagged": False,
                "answered": False,
                "forwarded": False,
                "flags": ["\\Recent"],
                "deleted": False,
                "to": [{"name": "Bob Jones", "email": "bob@example.com"}],
                "from": {"name": "Alice Smith", "email": "alice@example.com"},
                "cc": [{"name": "David", "email": "david@example.com"}],
                "reply_to": [],
                "subject": "Important Meeting Tomorrow",
                "date": "Tue, 17 Dec 2024 14:30:00 +0100",
                "return_path": "<alice@example.com>",
                "contents": [
                    {"content": "Hello,\n\nThis is the body of the email...\n\nBest regards,\nAlice", "contentType": "text/plain", "shouldDisplayAttachment": False},
                    {"content": "<p>Hello,<br><br>This is the body of the email...</p><p>Best regards,<br>Alice</p>", "contentType": "text/html", "shouldDisplayAttachment": False}
                ],
                "has_attachment": True,
                "attachments": [
                    {
                        "filename": "document.pdf",
                        "contentType": "application/pdf",
                        "size": 45678,
                        "extension": "pdf"
                    }
                ],
                "is_signed": True,
                "certificates": [],
                "priority": 1,
                "should_ask_receipt": False,
                "metadatas": [
                    {
                        "mail_type": "normal",
                        "mail_type_data": {}
                    }
                ]
            }
        }



class MailListResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails response
    """
    data = fields.List(fields.Dict(), required=False, allow_none=True)

    @staticmethod
    def sort_by_values() -> set:
        """
        return values available for sorting by
        """
        return {"date", "size", "subject", "to", "from", "cc"}

    @staticmethod
    def filter_by_values() -> set:
        """
        return values available for sorting by
        """
        return {"contents"}

    @classmethod
    def example(cls) -> dict:
        """Example response for mail list.
        
        :return: Example mail list response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [
                {
                    "uid": "42",
                    "size": 12543,
                    "seen": False,
                    "flagged": False,
                    "answered": False,
                    "forwarded": False,
                    "flags": ["\\Recent"],
                    "deleted": False,
                    "to": [{"name": "Bob Jones", "email": "bob@example.com"}],
                    "from": {"name": "Alice Smith", "email": "alice@example.com"},
                    "cc": [{"name": "David", "email": "david@example.com"}],
                    "reply_to": [],
                    "subject": "Important Meeting Tomorrow",
                    "date": "Tue, 17 Dec 2024 14:30:00 +0100",
                    "return_path": "<alice@example.com>",
                    "contents": [
                        {"content": "Hello,\n\nThis is the body of the email...\n\nBest regards,\nAlice", "contentType": "text/plain", "shouldDisplayAttachment": False}
                    ],
                    "has_attachment": True,
                    "attachments": [
                        {
                            "filename": "document.pdf",
                            "contentType": "application/pdf",
                            "size": 45678,
                            "extension": "pdf"
                        }
                    ],
                    "is_signed": True,
                    "certificates": [],
                    "priority": 3,
                    "should_ask_receipt": False,
                    "mail_type": [],
                    "mail_type_data": []
                }
            ]
        }


class MailDeleteResponseSchema(ApiBaseResponse):
    """
    Schema for DELETE /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid> response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for mail deletion.
        
        :return: Example mail deletion response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "uid_deleted": 42
            }
        }


class MailBulkDeleteResponseSchema(ApiBaseResponse):
    """
    Schema for deleting multiple mails response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for bulk mail deletion.
        
        :return: Example bulk deletion response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "deleted_ids": [1, 2, 3, 4, 5]
            }
        }


class MailMoveResponseSchema(ApiBaseResponse):
    """
    Schema for moving mails response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for moving mails.
        
        :return: Example mail move response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "moved_ids": [1, 2, 3]
            }
        }


class MailRawResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid>/raw response
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for raw mail content.
        
        :return: Example raw mail response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "raw": "Return-Path: <alice@example.com>\nReceived: from mail.example.com...\nDate: Tue, 17 Dec 2024 14:30:00 +0100\nFrom: Alice Smith <alice@example.com>\nTo: Bob Jones <bob@example.com>\nSubject: Meeting Tomorrow\n\nHello Bob,\n\nLet's meet tomorrow at 10am.\n\nBest regards,\nAlice"
            }
        }


class MailEditResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid>/edit response.

    Returns the full mail content along with the newly created tmp_draft ``key`` so the
    caller can subsequently use the draft API to modify and send the mail.
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for opening a mail for editing.

        :return: Example mail-edit response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                "uid": "42",
                "subject": "Important Meeting Tomorrow",
                "from": {"name": "Alice Smith", "email": "alice@example.com"},
                "to": [{"name": "Bob Jones", "email": "bob@example.com"}],
                "cc": [],
                "contents": [
                    {"content": "Hello,\n\nBest regards,\nAlice", "contentType": "text/plain", "shouldDisplayAttachment": False}
                ],
                "has_attachment": False,
                "attachments": []
            }
        }


class MailReplyResponseSchema(MailDetailResponseSchema):
    """Response schema for the reply endpoint.

    Extends MailDetailResponseSchema with reply-specific fields:
    - key: the tmp_draft key for the new reply draft
    - to: single contact dict (the original sender, overrides the list from MailDetailResponseSchema)
    - cc: list of contacts (original mail's Cc, only present when all=true)
    """

    key = fields.Str(
        required=True,
        metadata={"description": "The tmp_draft key for the new reply draft"},
    )

    @classmethod
    def example(cls) -> dict:
        base = MailDetailResponseSchema.example()
        base["key"] = "abc123def456"
        base["cc"] = [{"email": "cc@example.com", "name": "CC Person"}]
        return base


class MailListQuerySchema(Schema):
    """Schema for mail list query parameters."""

    page = fields.Int(
        validate=validate.Range(min=1),
        load_default=1,
    )
    per_page = fields.Int(
        validate=validate.Range(min=1, max=100),
        load_default=20,
    )