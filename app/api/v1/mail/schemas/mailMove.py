from marshmallow import Schema, fields

class MailMoveSchema(Schema):
    """
    Schema for moving multiple mails to another folder
    """
    mail_ids = fields.List(fields.Integer(), required=True)
    to_folder_id = fields.String(required=True)
