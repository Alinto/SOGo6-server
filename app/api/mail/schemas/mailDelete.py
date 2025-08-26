from marshmallow import Schema, fields

class MailDeleteSchema(Schema):
    """
    Schema for deleting emails.
    """
    mail_ids = fields.List(fields.Integer(), required=True)
