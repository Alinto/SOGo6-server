from marshmallow import Schema, fields, validate
from app.utils.api.ApiResponse import ApiBaseResponse

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
