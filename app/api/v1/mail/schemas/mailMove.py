from marshmallow import Schema, fields

class MailMoveSchema(Schema):
    """
    Schema for moving multiple mails to another folder
    """
    mail_uids = fields.List(fields.Integer(), required=True)
    to_folder_name = fields.String(required=True)
