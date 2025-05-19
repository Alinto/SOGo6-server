# -*- coding: utf-8 -*-

"""
Defines all domains parameters
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, post_load, post_dump


#As it was often written "ldap fields or SQL columns", a shorcut was made: "sqldap field"
class UserSource(Schema):
    """
    Schema for an agnostic User Source
    """
    US_TYPE = fields.String(required=True, validate=validate.OneOf(('ldap', 'sql'))) #Type of the user source
    US_ID   = fields.String(required=True) #must be unique

    US_MAIL = fields.List(fields.String(), load_default=['mail'], dump_default=['mail']) #Name of the sqldap field with the user's mail/alias
    US_SEARCH = fields.List(fields.String()) #Array of sqldap field used for autocompletion/search of user
    US_IMAP_LOGIN = fields.String() ##sqldap field where to fetch the imap login for a user (default to UIDFieldName for ldap or c_uid for sql)

    US_PWD_ALGO = fields.String() #TODO Algo used to encrypt the user password for login. Decide which algo bases on SOGo5 ones.
    US_CAN_AUTH = fields.Boolean(required=True) #The users in this US can authenticate
    US_IS_ADDRESSBOOK = fields.Boolean(required=True) #This US is shown for autocompletion and shared address book
    US_DISPLAY_NAME   = fields.String() #HUman readable name og this US, will ude US_ID if not set
    US_AUTO_SEARCH    = fields.Boolean(load_default=False, dump_default=False) #Auto return all users of the US whitout typinh any char in the search bar.

    #Resource
    US_KIND = fields.String() #sqldap field where to check if a user is a resource or not
    US_RESOURCE_MULTIBOOKING = fields.String() #sqldap field where to check how much time a resource can be booked simultaneously


class LdapUserSource(UserSource):
    """
    Schema for LDAP User Source
    Add specific LDAP settings
    """
    LDAP_HOSTNAME = fields.Url(required=True, schemes={'ldap', 'ldaps'})

    LDAP_CN         = fields.String(required=True) #field name to use for the common name typically 'cn'
    LDAP_ID         = fields.String(required=True) #field name to use for the common name typically 'cn'
    LDAP_UID        = fields.String(required=True) #field name for unique id of user typically 'uid'
    LDAP_BASE_DN    = fields.String(required=True) #Example: 'dc=example,dc=com'
    LDAP_FILTER     = fields.String() #Additional filter for ldap query
    LDAP_SCOPE      = fields.String(dump_default="SUB", load_default="SUB", validate=validate.OneOf(('BASE', 'ONE', 'SUB')))
    LDAP_PWD_POLICY = fields.Boolean(dump_default=False, load_default=False) # set to true if ldap has passwpord policy
    LDAP_SAMBA_PWD  = fields.Boolean(dump_default=False, load_default=False) # set to true if ldap has samba extension


    LDAP_BIND_DN      = fields.String(required=True)#The bind DN used to authnetify against the ldap server
    LDAP_BIND_PWD     = fields.String(required=True) #The password for the bindDN
    LDAP_BIND_AS_USER = fields.Boolean(load_default=False, dump_default=False) #After the fist auth, use the user's DN for the bind DN
    LDAP_BIND_FIELD   = fields.List(fields.String())  #Additionnal field to use when doing a bind
    LDAP_LOOKUP_FIELD = fields.List(fields.String(), load_default=['*'], dump_default=['*'])

    US_SEARCH = fields.List(fields.String(), load_default=['sn', 'displayName', 'cn', 'mail', 'telephoneNumber']) #Array of sqldap field used for autocompletion/search of user
    US_IMAP_LOGIN = fields.String() ##sql column where to fetch the imap login for a user, default to LDAP_UID value.

    @validates_schema
    def check_type(self, data, **_):
        """
        Check the type of User Source
        """
        if data["TYPE"] != "ldap":
            raise ValidationError("LdapUserSource set without TYPE being 'ldap'")

    @post_load
    def set_imap_login_load(self, data, **_):
        """
        if not set, the value of US_IMAP_LOGIN is the value of LDAP_UID.
        """
        if not 'US_IMAP_LOGIN' in data:
            data["US_IMAP_LOGIN"] = data["LDAP_UID"]
        return data

    @post_dump
    def set_imap_login_dump(self, data, **_):
        """
        if not set, the value of US_IMAP_LOGIN is the value of LDAP_UID.
        """
        if not 'US_IMAP_LOGIN' in data:
            data["US_IMAP_LOGIN"] = data["LDAP_UID"]
        return data

class SQLUserSource(UserSource):
    """
    Schema for SQL User Source
    Add specific SQL settings
    """

    US_SEARCH = fields.List(fields.String(), load_default=['mail', 'c_cn']) #Array of sqldap field used for autocompletion/search of user
    US_IMAP_LOGIN = fields.String(load_default="c_uid", dump_default="c_uid") ##sql column where to fetch the imap login for a user 


    @validates_schema
    def check_type(self, data, **_):
        """
        Check the type of User Source
        """
        if data["TYPE"] != "sql":
            raise ValidationError("SQLUserSource set without TYPE being 'sql'")

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

    #Login settings
    #SOGO_D_LOGIN_CHECK_MAX_ATTEMPT: max login attept a user can make during SOGO_D_LOGIN_CHECK_TIME_SPAN second. If limit is reach, it will be block for
    #SOGO_D_LOGIN_CHECK_BLOCK_TIME seconds. SOGO_D_LOGIN_CHECK_MAX_ATTEMPT = 0 disable any checking.
    SOGO_D_LOGIN_CHECK_MAX_ATTEMPT = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Number of failed attempt during SOGO_D_LOGIN_CHECK_TIME_SPAN before blocking
    SOGO_D_LOGIN_CHECK_TIME_SPAN   = fields.Integer(load_default=10, dump_default=10,validate=validate.Range(min=5)) #Time span when user can do SOGO_D_LOGIN_CHECK_MAX_ATTEMPT failed login attempt
    SOGO_D_LOGIN_CHECK_BLOCK_TIME  = fields.Integer(load_default=300, dump_default=300,validate=validate.Range(min=5)) #Time span where a user is forbidden to login after too many fail attempt.

    #Mailing -> Settings should be defined by the smtp server. But theyr are here to avoid making a smtp requets and reflect its rules.
    #SOGO_D_MAIL_MAX_SUBMISSION: max mail a user can send during SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL second. If limit is reach, it will be block for
    #SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl seconds. SOGO_D_MAIL_MAX_SUBMISSION = 0 disable any checking.
    SOGO_D_MAIL_MAX_SUBMISSION                = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0))
    SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL       = fields.Integer(load_default=30, dump_default=30, validate=validate.Range(min=10))
    SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl = fields.Integer(load_default=300, dump_default=300, validate=validate.Range(min=5))
    #TODO: for this kind of case, add a param to define exempt uid? For exemple a ressource room that could sned a lot of mail...

    #Maximum recipient a user sand an email too
    SOGO_D_MAIL_MAX_RECIPIENT = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0))

    #Password
    SOGO_D_PWD_RECOVERY = fields.Boolean(load_default=True, dump_default=True) #Enable or not users to set a method for password recovery
    SOGO_D_PWD_FORCE_RECOVERY = fields.Boolean(load_default=False, dump_default=False) #Force users to set a recovery method, overwrite SOGO_D_PWD_RECOVERY

    #Webserver max request from a user
    #SOGO_D_API_MAX_REQUEST: max api request a user can make during SOGO_D_API_MAX_REQUEST_INTERVAL second. If limit is reach, it will be block for
    #SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL seconds. SOGO_D_API_MAX_REQUEST = 0 disable any checking.
    #Beware that a user can make many request naturally, only used to block bot/ddos with value of ~100
    SOGO_D_API_MAX_REQUEST                = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0))
    SOGO_D_API_MAX_REQUEST_INTERVAL       = fields.Integer(load_default=30, dump_default=30, validate=validate.Range(min=10))
    SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL = fields.Integer(load_default=300, dump_default=300, validate=validate.Range(min=5))


    @validates_schema(skip_on_field_errors=True)
    def validate_auth_settings(self, data: dict, **_):
        """
        If SOGO_D_AUTH_TYPE = 'cas', check the other value
        """
        if data["SOGO_D_AUTH_TYPE"] == "cas":
            if {"SOGO_D_CAS_URL", "SOGO_D_CAS_LOGOUT_ENABLED"} not in set(data):
                raise ValidationError("Parameters among 'SOGO_D_CAS_URL', 'SOGO_D_CAS_LOGOUT_ENABLED' are missing")


