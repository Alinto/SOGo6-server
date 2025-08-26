from marshmallow import Schema, fields

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
    id = fields.String()
    subject = fields.String()
    from_ = fields.Nested(AddressSchema)
    to = fields.List(fields.Nested(AddressSchema))
    date = fields.String()
    seen = fields.Boolean()
    flagged = fields.Boolean()
    deleted = fields.Boolean()
    flags = fields.List(fields.String())
    hasAttachment = fields.Boolean()

class MailMessageListResponseSchema(Schema):
    """
    Schema for the response of mail list in a folder
    """
    status = fields.Boolean(required=True)
    mails = fields.List(fields.Nested(MailMessageSchema), required=True)
    errors = fields.String(allow_none=True)
