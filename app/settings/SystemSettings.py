# -*- coding: utf-8 -*-

"""
Defines all system settings.
Settings that defines the whole application behaviour but are not needed to start the webserver
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

class DomainSettings(Schema):
    """
    Schema for system settings
    """
    #Admin
    SOGO_S_DO_DOMAIN    = fields.Boolean(load_default=False, dump_default=False) #Allowed to have different rules according to domains
    SOGO_S_DOMAINS      = fields.List(fields.String()) #Domain set byt admin with custom rules
    SOGO_S_KNOWN_DOMAIN = fields.List(fields.String()) #List of domains that sogo should known. To use if they are restriction rule like SOGO_S_REJECT_UNKNOWN_DOMAIN
                                                       #and the domains are not list or set in domains rules.

    #Login
    SOGO_S_REJECT_UNKNOWN_DOMAIN = fields.Boolean(load_default=False, dump_default=False) #Only allow login requets with mail domain known by sogo (SOGO_S_DOMAINS)
                                                                                          #or list in SOGO_S_KNOWN_DOMAIN
