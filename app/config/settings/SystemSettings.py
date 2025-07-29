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
    SOGO_S_DOMAINS      = fields.List(fields.String()) #Domain set by admin to let sogo know
    SOGO_S_KNOWN_DOMAIN = fields.List(fields.String()) #List of domains that sogo should known. To use if they are restriction rule like SOGO_S_REJECT_UNKNOWN_DOMAIN
                                                       #and the domains are not list or set in domains rules.
    SOGO_D_IS_CONFIGURED = fields.Boolean(load_default=False, dump_default=False) #Bool to tell if sogo has been set up a first time or not

    #Login
    SOGO_S_REJECT_UNKNOWN_DOMAIN = fields.Boolean(load_default=False, dump_default=False) #Only allow login requets with mail domain known by sogo (SOGO_S_DOMAINS)
                                                                                          #or list in SOGO_S_KNOWN_DOMAIN
    SOGO_S_DOMAINLESS_LOGIN = fields.Boolean(load_default=False, dump_default=False) #Allow login with only yhe usernam/uid and not the full email.

    #Binary
    SOGO_S_SENDMAIL = fields.String(load_default="/usr/lib/sendmail", dump_default="/usr/lib/sendmail") #Admin can decide to use sendmail instead of smtp.
    SOGO_S_ZIP = fields.String(load_default="/usr/bin/zip", dump_default="/usr/bin/zip") #Binary path od the zip binary
                                                                                         #TODO not used, it's python that decides what to use

    #Paths
    SOGO_S_MAILSPOOL_PATH = fields.String(load_default="/var/spool/sogo", dump_default="/var/spool/sogo") #Path where temp draft messages are stored
