"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines the input and ouput for ApiAdminConfig.
"""

from marshmallow import Schema, fields

class AdminConfigSetting(Schema):
    """
    Schema of a simple setting
    """
    name  = fields.String()
    value = fields.Raw()

class AdminConfigSystemPostSchema(Schema):
    """
    Schema of the body expected for posting system settings
    """
    settings  = fields.Dict(keys=fields.String(), values=fields.Raw())
