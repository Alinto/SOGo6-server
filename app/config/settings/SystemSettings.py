# -*- coding: utf-8 -*-

"""
Defines all system settings.
Settings that defines the whole application behaviour but are not needed to start the webserver
"""
from typing import Type
from marshmallow import fields

from app.config.settings.SogoSchema import SogoSchema
from app.utils.config.generateObjFromSchema import SettingsObj

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

    is_needed_by_ui = {"SOGO_S_DIRECT_LOGIN",}

    #Admin
    SOGO_S_DO_DOMAIN    = fields.Boolean(load_default=False, dump_default=False) #Allowed to have different rules according to domains
    SOGO_S_KNOWN_DOMAIN = fields.List(fields.String()) #List of domains that sogo should known. To use if they are restriction rule like SOGO_S_REJECT_UNKNOWN_DOMAIN
                                                       #and the domains are not list or set in domains rules.

    #Login
    SOGO_S_REJECT_UNKNOWN_DOMAIN = fields.Boolean(load_default=False, dump_default=False) #Only allow login requets with mail domain known by sogo (SOGO_S_DOMAINS)
                                                                                          #or list in SOGO_S_KNOWN_DOMAIN
    SOGO_S_DOMAINLESS_LOGIN = fields.Boolean(load_default=False, dump_default=False) #Allow login with only the username/uid and not the full email.
    SOGO_S_DIRECT_LOGIN = fields.Boolean(load_default=False, dump_default=False) #Tell the UI to directly do the login mech configured (only one for all users/domains)

    #Binary
    SOGO_S_SENDMAIL = fields.String(load_default="/usr/lib/sendmail", dump_default="/usr/lib/sendmail") #Admin can decide to use sendmail instead of smtp.




class SystemSettingsObj(SettingsObj):
    """
    Obj with the fields of schema SystemSettings as attributes with the proper type
    """

    SOGO_S_DO_DOMAIN: bool = False
    SOGO_S_KNOWN_DOMAIN: list[str] = []
    SOGO_S_REJECT_UNKNOWN_DOMAIN: bool = False
    SOGO_S_DOMAINLESS_LOGIN: bool = False
    SOGO_S_DIRECT_LOGIN: bool = False
    SOGO_S_SENDMAIL: str = "/usr/lib/sendmail"

