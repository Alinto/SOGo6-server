# -*- coding: utf-8 -*-

"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the schema needed by ApiMailAccount.py
"""

from marshmallow import Schema, fields

class MailAccountSchema(Schema):
    """
    Schema for one mail account
    """
    name = fields.String()
    mail = fields.Email()
    id   = fields.Integer()

class ListMailAccountsResponse(Schema):
    """
    Schema of an account's list
    """
    accounts = fields.List(fields.Nested(MailAccountSchema))


class ListMailAccountsDelegation(Schema):
    """
    Shema with a list of mail for delegations
    """
    accounts = fields.List(fields.Email())


