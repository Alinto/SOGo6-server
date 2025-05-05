# -*- coding: utf-8 -*-

import marshmallow as ma


class RetGetUserPreferences(ma.Schema):
    """
    Schema to get user's preferences response
    """
    language = ma.fields.String()

class SaveSchema(ma.Schema):
    """
    Shema for the save user's preferences request
    """
    language = ma.fields.String()
