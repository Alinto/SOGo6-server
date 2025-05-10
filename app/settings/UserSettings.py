# -*- coding: utf-8 -*-

"""
Defines all users parameters
"""

import zoneinfo

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

class DomainSettings(Schema):
    """
    Schema for user settings
    """

    #Timezone #TODO the timezones depends of the OS system and may be incomplete -> read https://docs.python.org/3/library/zoneinfo.html
    SOGO_U_TIMEZONE = fields.String(validate=validate.OneOf(zoneinfo.available_timezones()))

    #Language #TODO do we need to validate available language here? Or this is just frontend work?
    SOGO_U_LANGUAGE = fields.String(load_default="English", dump_default="English")

    #Folders
    SOGO_U_FOLDER_CREATION_NOTIF = fields.Boolean(load_default=True, dump_default=True) #Send mail notification when user create a calenanr or addrebook
