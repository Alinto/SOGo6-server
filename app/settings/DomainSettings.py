# -*- coding: utf-8 -*-

"""
Defines all domains parameters
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.utils.dictionnaries import DictSettings



class DomainSettings(Schema):
    """
    Schema for domains settings
    """
    #Admin
    SOGO_D_PWD_CHANGE_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to change the password (for ldap it means the ldap admin account is allow to do that too)


    #Type of authentication protocol used for this domain. Beware that if the value is not plain, more parameters are needed
    SOGO_D_AUTH_TYPE = fields.String(load_default="plain", dump_default="plain",
                                     validate=validate.OneOf(('plain', 'openid', 'cas', 'saml2')))

    #If SOGO_D_AUTH_TYPE = 'cas'
    SOGO_D_CAS_URL            = fields.Url(schemes={'http','https'}) #Url of the CAS server
    SOGO_D_CAS_LOGOUT_ENABLED = fields.Boolean() # Allowed or not users to logout from sogo (invalidate the ticket for all others application)

    #Enable DAV access to calendars and addressbooks.
    SOGO_D_DAV_CONTACT_ENABLED  = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_DAV_CALENDAR_ENABLED = fields.Boolean(load_default=True, dump_default=True)

    #Calendar Settings
    SOGO_D_JITSI_LINK_ENABLED = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_JITSI_BASE_URL     = fields.Url(schemes={'http','https'})

    #Folder settings
    SOGO_D_DAV_PUBLIC_ACCESS_ENABLE        = fields.Boolean(load_default=False, dump_default=False) #Enable or not public dav access
    SOGO_D_FOLDER_DISABLE_EXPORT           = fields.List(fields.String(validate=validate.OneOf(('mail', 'calendar', 'contact')))) #Disable or not folder export
    SOGO_D_FOLDER_DISABLE_SHARING          = fields.List(fields.String(validate=validate.OneOf(('mail', 'calendar', 'contact')))) #Disable or not folder sharing
    SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH = fields.List(fields.String(validate=validate.OneOf(('mail', 'calendar', 'contact')))) #Disable or not folder sharing to any authenticated user from the domain
    SOGO_U_FOLDER_CREATION_NOTIF           = fields.Boolean(load_default=True, dump_default=True) #Send mail notif to user when theyself or another with correct acl create a folder.
    SOGO_D_AUTOCOMPLETION_MIN_LEN          = fields.Integer(load_default=2, dump_default=2, validate=validate.Range(min=2)) #Number of (chars needed - 1) to trigger the autocompletion search. At 2 it will trigger for the third char.


    @validates_schema(skip_on_field_errors=True)
    def validate_auth_settings(self, data: dict, **kwargs): #TODO check if kwargs can be removed
        """
        If SOGO_D_AUTH_TYPE = 'cas', check the other value
        """
        if data["SOGO_D_AUTH_TYPE"] == "cas":
            if {"SOGO_D_CAS_URL", "SOGO_D_CAS_LOGOUT_ENABLED"} not in set(data):
                raise ValidationError("Parameters among 'SOGO_D_CAS_URL', 'SOGO_D_CAS_LOGOUT_ENABLED' are missing")
        
