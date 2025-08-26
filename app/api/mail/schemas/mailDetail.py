"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines the schema for detailed mail information, used by ApiMailDetail.py
"""

from marshmallow import Schema, fields

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
    from_ = fields.String() #TODO: `from` is a reserved keyword, replace it in UI?
    to = fields.List(fields.String())
    cc = fields.List(fields.String())
    bcc = fields.List(fields.String())
    size = fields.Integer()
    imageBlocked = fields.Boolean()
    body = fields.String()
    attachments = fields.Nested(AttachmentsSchema)

class MailDetailResponseSchema(Schema):
    """
    Schema for the response of the mail detail endpoint
    """
    status = fields.Boolean(required=True)
    errors = fields.String(allow_none=True)
    mail = fields.Nested(MailDetailSchema, allow_none=True)
