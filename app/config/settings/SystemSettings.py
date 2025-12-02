# -*- coding: utf-8 -*-

"""
Defines all system settings.
Settings that defines the whole application behaviour but are not needed to start the webserver
"""
from dataclasses import dataclass, MISSING
from dataclasses import field as dc_field
from dataclasses import fields as dc_fields
from typing import Type
from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.config.settings.SogoSchema import SogoSchema


def get_all_system_schemas() -> list[Type[SogoSchema]]:
    """
    Return a list with all Sogo Domain Schema classes

    :return: List with all domain schem classes
    :rtype: list[Type[SogoSchema]]
    """
    all_schemas: list[Type[SogoSchema]] = [SystemSettings]
    return all_schemas

class SystemSettings(SogoSchema):
    """
    Schema for system settings
    """
    subparent = "SYSTEM_SETTINGS"

    #Admin
    SOGO_S_DO_DOMAIN    = fields.Boolean(load_default=False, dump_default=False) #Allowed to have different rules according to domains
    SOGO_S_KNOWN_DOMAIN = fields.List(fields.String()) #List of domains that sogo should known. To use if they are restriction rule like SOGO_S_REJECT_UNKNOWN_DOMAIN
                                                       #and the domains are not list or set in domains rules.

    #Login
    SOGO_S_REJECT_UNKNOWN_DOMAIN = fields.Boolean(load_default=False, dump_default=False) #Only allow login requets with mail domain known by sogo (SOGO_S_DOMAINS)
                                                                                          #or list in SOGO_S_KNOWN_DOMAIN
    SOGO_S_DOMAINLESS_LOGIN = fields.Boolean(load_default=False, dump_default=False) #Allow login with only the username/uid and not the full email.

    #Binary
    SOGO_S_SENDMAIL = fields.String(load_default="/usr/lib/sendmail", dump_default="/usr/lib/sendmail") #Admin can decide to use sendmail instead of smtp.

    #Paths
    SOGO_S_MAILSPOOL_PATH = fields.String(load_default="/var/spool/sogo", dump_default="/var/spool/sogo") #Path where temp draft messages are stored



class SystemSettingsObj:
    """
    Typed equivalent of the original Marshmallow schema.
    """

    # Admin
    SOGO_S_DO_DOMAIN: bool = False
    SOGO_S_KNOWN_DOMAIN: list[str] = []

    # Login
    SOGO_S_REJECT_UNKNOWN_DOMAIN: bool = False
    SOGO_S_DOMAINLESS_LOGIN: bool = False

    # Binary
    SOGO_S_SENDMAIL: str = "/usr/lib/sendmail"

    # Paths
    SOGO_S_MAILSPOOL_PATH: str = "/var/spool/sogo"

    def __init__(self, data: dict = None):
        """
        Initialize attributes from a dict having the same keys
        as the class fields.
        Missing values fall back to defaults.
        """
        data = data or {}

        for key, default_value in data.items():
            # Restore default — but clone lists to prevent shared mutability
            if isinstance(default_value, list):
                setattr(self, key, list(default_value))
            else:
                setattr(self, key, default_value)