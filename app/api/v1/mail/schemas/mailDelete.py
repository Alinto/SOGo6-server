from marshmallow import Schema, fields

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
