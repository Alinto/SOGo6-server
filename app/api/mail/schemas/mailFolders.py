# -*- coding: utf-8 -*-

"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the schema needed by ApiMailFolder.py
"""

from marshmallow import Schema, fields

class MailFolderSchema(Schema):
    """
    Schema for one mail account
    """
    name  = fields.String()
    type  = fields.String()
    flags = fields.List(fields.String())
    subscribed = fields.Boolean()
    children = fields.List(fields.Nested(lambda: MailFolderSchema()))



class ListMailFolders(Schema):
    """
    Schema of an account's list
    """
    folders = fields.List(fields.Nested(MailFolderSchema))

