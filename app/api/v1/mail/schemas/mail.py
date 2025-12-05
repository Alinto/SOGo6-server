from marshmallow import Schema, fields, validate
from app.utils.api.ApiBaseResponse import ApiBaseResponse

class MailDeleteSchema(Schema):
    """
    Schema for deleting emails.
    """
    mail_uids = fields.List(fields.Integer(), required=True)

class MailFolderQueryArgsSchema(Schema):
    """
    Schema for query parameters when deleting emails in a folder.
    """
    before_date = fields.String(required=False, allow_none=True)


class AttachmentPartSchema(Schema):
    """
    Schema for an attachment part in an email
    """
    partId = fields.String()
    name = fields.String()
    contentType = fields.String()
    size = fields.Integer()
    downloadUri = fields.String()
    displayUri = fields.String()

class AttachmentsSchema(Schema):
    """
    Schema for the attachments group in a mail
    """
    parts = fields.List(fields.Nested(AttachmentPartSchema))
    zipUri = fields.String()
    count = fields.Integer()

class MailDetailSchema(Schema):
    """
    Schema for detailed mail information
    """
    id = fields.String()
    contentUri = fields.String()
    seen = fields.Boolean()
    answered = fields.Boolean()
    recent = fields.Boolean()
    deleted = fields.Boolean()
    hasAttachment = fields.Boolean()
    important = fields.Boolean()
    date = fields.Integer()
    subject = fields.String()
    isMailingList = fields.Boolean()
    from_ = fields.String(data_key="from")
    to = fields.List(fields.String())
    cc = fields.List(fields.String())
    bcc = fields.List(fields.String())
    size = fields.Integer()
    imageBlocked = fields.Boolean()
    body = fields.String()
    attachments = fields.Nested(AttachmentsSchema)

class MailDetailResponseSchema(ApiBaseResponse):
    """
    Schema for the response of the mail detail endpoint
    """
    data = fields.Dict(required=True, metadata={
        'description': 'Contains the mail detail',
        'example': {'mail': {}}
    })


class AddressSchema(Schema):
    """
    Schema for an email address
    """
    name = fields.String()
    email = fields.String()

class MailMessageSchema(Schema):
    """
    Schema for one mail message
    """
    uid = fields.String()
    subject = fields.String()
    from_ = fields.String(data_key="from")
    to = fields.List(fields.Nested(AddressSchema))
    date = fields.String()
    seen = fields.Boolean()
    flagged = fields.Boolean()
    deleted = fields.Boolean()
    flags = fields.List(fields.String())
    hasAttachment = fields.Boolean()

class MailMessageListResponseSchema(ApiBaseResponse):
    """
    Schema for the response of mail list in a folder
    """
    data = fields.List(
        fields.Nested(MailMessageSchema),
        required=True,
        metadata={
            'description': 'List of mail messages',
            'example': [
                {'uid': '1', 'subject': 'Test', 'from': {'name': 'Alice', 'email': 'a@example.com'}}
            ]
        }
    )

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
