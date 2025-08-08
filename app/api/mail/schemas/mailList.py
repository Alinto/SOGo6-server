# -*- coding: utf-8 -*-

"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the schema needed by ApiMailFolder.py
"""

from marshmallow import Schema, fields


class EmailAddressSchema(Schema):
    """
    Schema for email addresses (from/to fields)
    """
    name = fields.String()
    email = fields.Email()


class MailMessageListSchema(Schema):
    """
    Schema for a single mail message to display in the list
    """
    id = fields.String()
    subject = fields.String()
    from_ = fields.Nested(EmailAddressSchema, data_key="from")  #TODO: `from` is a reserved keyword; replace it in UI?
    to = fields.List(fields.Nested(EmailAddressSchema))
    date = fields.String()
    seen = fields.Boolean()
    flagged = fields.Boolean()
    hasAttachment = fields.Boolean()
    snippet = fields.String()

