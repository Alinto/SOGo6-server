# -*- coding: utf-8 -*-

"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the schema needed by ApiMailAccount.py
"""

from marshmallow import Schema, fields
from app.utils.api.ApiResponse import ApiBaseResponse

class MailAccountSchema(Schema):
    """
    Schema for one mail account
    """
    name = fields.String()
    mail = fields.Email()
    id   = fields.Integer()

class ListMailAccountsResponse(ApiBaseResponse):
    """
    Schema of an account's list
    """
    data = fields.Dict(required=True, metadata={
        'description': 'Contains the accounts list',
        'example': {'accounts': []}
    })


class ListMailAccountsDelegation(ApiBaseResponse):
    """
    Schema with a list of mail for delegations
    """
    data = fields.Dict(required=True, metadata={
        'description': 'Contains the delegation accounts list',
        'example': {'accounts': []}
    })
