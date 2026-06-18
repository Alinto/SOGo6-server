from marshmallow import Schema, fields, validate
from app.utils.api.ApiBaseResponse import ApiBaseResponse

class SaveDraftQuerySchema(Schema):
    """Query parameters for PUT /<key>/save."""
    close = fields.Boolean(load_default=False, metadata={"description": "If true, delete the tmp_draft entry after saving (the IMAP draft is kept)."})

class SaveDraftSchema(Schema):
    """
    Schema for POST /mailboxes/<account_id>/mail/save - Save a mail as a draft.
    All fields are optional since a draft may be incomplete.
    """
    from_addr = fields.Email(required=False, allow_none=True, data_key="from")
    to = fields.List(fields.Email(), required=False, load_default=[])
    subject = fields.String(required=False, load_default="")
    body = fields.String(required=False, load_default="")
    cc = fields.List(fields.Email(), required=False, load_default=[])
    bcc = fields.List(fields.Email(), required=False, load_default=[])
    return_receipt = fields.Boolean(required=False, allow_none=True, load_default=None)
    priority = fields.Integer(required=False, allow_none=True, load_default=None, validate=validate.OneOf([1, 2, 3, 4, 5]), metadata={"description": "Email priority (1=highest, 5=lowest)"})
    is_html = fields.Boolean(required=False, load_default=False, metadata={"description": "If true, create multipart/alternative with both text/plain and text/html; if false, only text/plain"})
    reply_to = fields.String(required=False, allow_none=True, load_default=None, metadata={"description": "Reply-To email address or 'Name <email>' format"})

    @classmethod
    def example(cls) -> dict:
        """Example data for saving a draft.

        :return: Example save draft payload
        :rtype: dict
        """
        return {
            "from": "user@example.com",
            "to": ["recipient@example.com"],
            "subject": "Draft subject",
            "body": "Draft body content",
            "cc": [],
            "bcc": [],
            "priority": 3,
            "is_html": True,
            "reply_to": "jdoe@example.com"
        }


class UploadAttachmentResponseSchema(ApiBaseResponse):
    """
    Schema for response when uploading an attachment to a draft.
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for uploading an attachment.

        :return: Example upload attachment response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                "filename": "myfile.txt"
            }
        }


class SaveDraftResponseSchema(ApiBaseResponse):
    """
    Schema for response when saving a mail draft.
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for saving a draft.

        :return: Example save draft response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                "uid": "123",
                "subject": "Draft subject",
                "from": "user@example.com",
                "to": ["recipient@example.com"],
                "body": "Draft body content"
            }
        }

class UploadAttachmentFileSchema(Schema):
    """
    Schema for uploading a file attachment.
    """
    file = fields.Raw(
        required=True,
        metadata={
            "type": "string",
            "format": "binary",
            "description": "Attachment file",
        },
    )


class SendMailQuerySchema(Schema):
    """
    Query parameters for POST /mailboxes/<account_id>/send
    """
    key = fields.String(required=False, load_default=None, allow_none=True, metadata={"description": "tmp_draft key; if provided the tmp_draft entry is checked and deleted after a successful send"})


class SendMailSchema(Schema):
    """
    Schema for POST /mailboxes/<account_id>/send - Send an email
    """
    from_addr = fields.Email(required=True, data_key="from")
    to = fields.List(fields.Email(), required=True, validate=validate.Length(min=1))
    subject = fields.String(required=False, load_default="")
    body = fields.String(required=False, load_default="")
    cc = fields.List(fields.Email(), required=False, load_default=[])
    bcc = fields.List(fields.Email(), required=False, load_default=[])
    return_receipt = fields.Boolean(required=False, allow_none=True, load_default=None)
    priority = fields.Integer(required=False, allow_none=True, load_default=None, validate=validate.OneOf([1, 2, 3, 4, 5]), metadata={"description": "Email priority (1=highest, 5=lowest)"})
    is_html = fields.Boolean(required=False, load_default=False, metadata={"description": "If true, create multipart/alternative with both text/plain and text/html; if false, only text/plain"})
    reply_to = fields.String(required=False, allow_none=True, load_default=None, metadata={"description": "Reply-To email address or 'Name <email>' format"})

    @classmethod
    def example(cls) -> dict:
        """
        Simple example for sending a mail
        """
        return {
            "from": "sogo-tests1@example.org",
            "to": ["sogo-tests1@example.org"],
            "subject": "Hello",
            "body": "Hello world! commment ça va ?",
            "cc": [],
            "bcc": [],
            "return_receipt": None,
            "priority": 3,
            "is_html": True,
            "reply_to": None
        }


class SendMailResponseSchema(ApiBaseResponse):
    """
    Schema for response when sending a mail
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        example
        """
        return {}


class KeyQuerySchema(Schema):
    """
    Query parameters schema for endpoints that require a mandatory ``key`` parameter.
    """
    key = fields.String(required=True, metadata={"description": "tmp_draft key (mandatory)"})


class CurrentDraftItemSchema(Schema):
    """Schema for a single tmp_draft entry returned by /current."""
    key = fields.String()
    mail_server_uid = fields.String()
    locked = fields.Boolean()
    last_updated = fields.Integer(allow_none=True, metadata={"description": "Unix timestamp (seconds) of the last insert/update on this draft entry."})


class CurrentDraftsResponseSchema(ApiBaseResponse):
    """Schema for GET /current response."""
    data = fields.List(fields.Nested(CurrentDraftItemSchema), required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        example
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [
                {"key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4", "mail_server_uid": "42", "locked": False, "last_updated": 1749380000}
            ]
        }
