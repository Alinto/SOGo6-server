# -*- coding: utf-8 -*-

"""
Define all domains parameters
"""
from typing import Type
from marshmallow import fields, validate
from app.config.settings.SogoSchema import SogoSchema


def get_all_domain_schemas() -> list[Type[SogoSchema]]:
    """
    Return a list with all Sogo Domain Schema classes

    :return: List with all domain schem classes
    :rtype: list[Type[SogoSchema]]
    """
    all_schemas = [AuthSettings, UserSourceSettings, UserModuleSettings, MailSettings, CalendarContactSettings]
    return all_schemas


class AuthSettings(SogoSchema):
    """
    Schema for an Authentication
    """

    subparent = "AUTH_SETTINGS"
    dependencies = {
        "SOGO_D_CAS_URL": ("SOGO_D_AUTH_TYPE", "cas"),
        "SOGO_D_CAS_LOGOUT_ENABLED": ("SOGO_D_AUTH_TYPE", "cas"),

        "SOGO_D_OPENID_CONFIG_URL": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_CLIENT_NAME": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_CLIENT_SECRET": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_SCOPE": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_EMAIL": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_TOKEN_CHECK_INTERVAL": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_REFRESH_ENABLE": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_ENDSESSION_ENABLED": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGo_D_OPENID_FETCH_USER_PROFILE": ("SOGO_D_AUTH_TYPE", "openid"),

        "SOGO_D_SAML2_URL": ("SOGO_D_AUTH_TYPE", "saml2"),

        "SOGO_D_PWD_CHANGE_ENABLED": ("SOGO_D_AUTH_TYPE", "plain"),
        "SOGO_D_LOGIN_CHECK_MAX_ATTEMPT": ("SOGO_D_AUTH_TYPE", "plain"),
        "SOGO_D_LOGIN_CHECK_TIME_SPAN": ("SOGO_D_AUTH_TYPE", "plain"),
        "SOGO_D_LOGIN_CHECK_BLOCK_TIME": ("SOGO_D_AUTH_TYPE", "plain"),
        "SOGO_D_PWD_RECOVERY": ("SOGO_D_AUTH_TYPE", "plain"),
        "SOGO_D_PWD_RECOVERY_METHOD": ("SOGO_D_PWD_RECOVERY", True),
        "SOGO_D_PWD_RECOVERY_FORCE": ("SOGO_D_PWD_RECOVERY", True),
        "SOGO_D_LOGIN_MFA": ("SOGO_D_AUTH_TYPE", "plain"),
        "SOGO_D_LOGIN_MFA_METHOD": ("SOGO_D_LOGIN_MFA", True),
        "SOGO_D_LOGIN_MFA_FORCE": ("SOGO_D_LOGIN_MFA", True),

    }
    is_secret = {"SOGO_D_OPENID_CLIENT_SECRET",}

    #Type of authentication protocol used for this domain. Beware that if the value is not plain, more parameters are needed
    SOGO_D_AUTH_TYPE = fields.String(load_default="plain", dump_default="plain",
                                     validate=validate.OneOf(('plain', 'openid', 'cas', 'saml2')))
    #If SOGO_D_AUTH_TYPE = 'cas'
    SOGO_D_CAS_URL            = fields.Url(schemes={'http','https'}, require_tld=False) #Url of the CAS server
    SOGO_D_CAS_LOGOUT_ENABLED = fields.Boolean() # Allowed or not users to logout from sogo (invalidate the ticket for all others application)

    #If SOGO_D_AUTH_TYPE = 'openid'
    SOGO_D_OPENID_CONFIG_URL           = fields.Url(schemes={'http','https'}, require_tld=False)
    SOGO_D_OPENID_CLIENT_NAME          = fields.String() #Name of the openid client
    SOGO_D_OPENID_CLIENT_SECRET        = fields.String() #Secret of the openid client
    SOGO_D_OPENID_SCOPE                = fields.String(load_default="openid profile email", dump_default="openid profile email") #Scope requested to the openis server
    SOGO_D_OPENID_EMAIL                = fields.String(load_default="email", dump_default="email") #parameter from user profile with the user's mail, to match with the user source
    SOGO_D_OPENID_TOKEN_CHECK_INTERVAL = fields.Integer(validate=validate.Range(min=0)) #Interval where a valid token is not checked again. 0 means always checked.
    SOGO_D_OPENID_REFRESH_ENABLE       = fields.Boolean(load_default=True, dump_default=True) # Allowed or not sogo to refresh token if the openid server has the mechanism
    SOGO_D_OPENID_ENDSESSION_ENABLED       = fields.Boolean(load_default=False, dump_default=False) # Allowed or not sogo to logout from the openid server instead of just the webmail
    SOGo_D_OPENID_FETCH_USER_PROFILE   = fields.Boolean(load_default=True, dump_default=True) # sogo will fetch the user profile to get the user's email. If no, directly fetch from the token.


    #IF SOGO_D_AUTH_TYPE = 'saml2'
    SOGO_D_SAML2_URL  = fields.Url(schemes={'http','https'}, require_tld=False) #TODO saml2 configuration....

    #If SOGO_D_AUTH_TYPE = 'plain'
    SOGO_D_PWD_CHANGE_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to change the password (for ldap it means the ldap admin account is allow to do that too)
    #SOGO_D_LOGIN_CHECK_MAX_ATTEMPT: max login attept a user can make during SOGO_D_LOGIN_CHECK_TIME_SPAN second. If limit is reach, it will be block for
    #SOGO_D_LOGIN_CHECK_BLOCK_TIME seconds. SOGO_D_LOGIN_CHECK_MAX_ATTEMPT = 0 disable any checking.
    SOGO_D_LOGIN_CHECK_MAX_ATTEMPT = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Number of failed attempt during SOGO_D_LOGIN_CHECK_TIME_SPAN before blocking
    SOGO_D_LOGIN_CHECK_TIME_SPAN   = fields.Integer(load_default=10, dump_default=10,validate=validate.Range(min=5)) #Time span when user can do SOGO_D_LOGIN_CHECK_MAX_ATTEMPT failed login attempt
    SOGO_D_LOGIN_CHECK_BLOCK_TIME  = fields.Integer(load_default=300, dump_default=300,validate=validate.Range(min=5)) #Time span where a user is forbidden to login after too many fail attempt.

    SOGO_D_PWD_RECOVERY = fields.Boolean(load_default=True, dump_default=True) #Enable or not users to set a method for password recovery
    SOGO_D_PWD_RECOVERY_METHOD = fields.List(fields.String(), validate=validate.ContainsOnly(('secretQuestion', 'secondaryEmail', 'apiCall')))
    SOGO_D_PWD_RECOVERY_FORCE = fields.Boolean(load_default=False, dump_default=False) #Force users to set a recovery method, overwrite SOGO_D_PWD_RECOVERY
    SOGO_D_PWD_RECOVERY_DELAY = fields.Integer() #Delay before the user can ask again for a password recovery
    SOGO_D_LOGIN_MFA = fields.Boolean(load_default=True, dump_default=True) #Enable or not users to set a MFA method for password
    SOGO_D_LOGIN_MFA_METHOD = fields.List(fields.String(), validate=validate.ContainsOnly(('totp',)))
    SOGO_D_LOGIN_MFA_FORCE = fields.Boolean(load_default=False, dump_default=False) #Force users to set a recovery method, overwrite SOGO_D_PWD_RECOVERY

class UserSourceSettings(SogoSchema):
    """
    Schema for an agnostic User Source
    """
 
    subparent = "USER_SOURCE"
    is_duplicable = True
    is_uid = "US_UID"
    dependencies = {
        "US_LDAP_HOSTNAME": ("US_TYPE", "ldap"),
        "US_LDAP_CN": ("US_TYPE", "ldap"),
        "US_LDAP_ID": ("US_TYPE", "ldap"),
        "US_LDAP_UID" : ("US_TYPE", "ldap"),
        "US_LDAP_BASE_DN": ("US_TYPE", "ldap"),
        "US_LDAP_FILTER": ("US_TYPE", "ldap"),
        "US_LDAP_SCOPE": ("US_TYPE", "ldap"),
        "US_LDAP_PWD_POLICY": ("US_TYPE", "ldap"),
        "US_LDAP_PWD_UPDATE_SAMBA": ("US_TYPE", "ldap"),
        "US_LDAP_QUERY_TIMEOUT": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_DN": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_DN_PWD": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_AS_USER": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_FIELD": ("US_TYPE", "ldap"),
        "US_LDAP_ATTR_FIELD": ("US_TYPE", "ldap"),
        "US_LDAP_GROUP_CLASS": ("US_TYPE", "ldap"),
        "US_SQL_USER_URL": ("US_TYPE", "sql"),
        "US_SQL_PREPEND_PWD_SCHEME": ("US_TYPE", "sql"),
        "US_SQL_USER_FILTER": ("US_TYPE", "sql"),
        "US_SQL_DOMAIN_FIELD": ("US_TYPE", "sql"),

        "US_PWD_ALGO": ("US_CAN_AUTH", True),
        "US_SIM_KEY_TYPE": ("US_PWD_ALGO", 'sym-aes-128-cbc'),
        "US_SIM_KEY_VALUE": ("US_PWD_ALGO", 'sym-aes-128-cbc'),

        "US_PWD_POLICY": ("US_CAN_AUTH", True),
        "US_PWD_LEN_MIN": ("US_PWD_POLICY", True),
        "US_PWD_LEN_MAX": ("US_PWD_POLICY", True),
        "US_PWD_UPPERCASE_MIN": ("US_PWD_POLICY", True),
        "US_PWD_LOWERCASE_MIN": ("US_PWD_POLICY", True),
        "US_PWD_DIGITS_MIN": ("US_PWD_POLICY", True),
        "US_PWD_SPECIAL_MIN": ("US_PWD_POLICY", True),
        "US_PWD_SPECIAL_ALLOWED": ("US_PWD_POLICY", True),

        "US_MAIL": ("US_CAN_AUTH", True),
        "US_MAIL_SERVER_LOGIN": ("US_CAN_AUTH", True),
        "US_MAIL_FILTERING_LOGIN": ("US_CAN_AUTH", True),
        "US_MAIL_OUTGOING_LOGIN": ("US_CAN_AUTH", True),

        "US_SEARCH": ("US_IS_ADDRESSBOOK", True),
        "US_DISPLAY_NAME": ("US_IS_ADDRESSBOOK", True),
        "US_AUTO_SEARCH": ("US_IS_ADDRESSBOOK", True),
        "US_AUTO_QUERY_LIMIT": ("US_IS_ADDRESSBOOK", True),
        "US_EXTRA_CONTACT_INFO": ("US_IS_ADDRESSBOOK", True),
        "US_HIDDEN_USER": ("US_IS_ADDRESSBOOK", True),

        "US_RESOURCE_SEARCH": ("US_HAS_RESOURCE", True),
        "US_RESOURCE_MULTIBOOKING": ("US_HAS_RESOURCE", True),
        "US_RESOURCE_EXTRA_INFO": ("US_HAS_RESOURCE", True),
    }
    is_required = {"US_LDAP_HOSTNAME", "US_LDAP_BIND_DN", "US_LDAP_BIND_DN_PWD",
                   "US_LDAP_BASE_DN", "US_LDAP_UID", "US_LDAP_CN", "US_LDAP_ID",
                   "US_SQL_USER_URL", "US_SQL_PREPEND_PWD_SCHEME"}
    
    is_secret = {"US_LDAP_BIND_DN_PWD",}

    PWD_ALGO = ('none', 'plain',
               'crypt',
               'md5','md5-crypt',
               'smd5', 'cram-md5', 'ldap-md5',
               'sha',
               'sha256', 'sha256-crypt', 'ssha256',
               'sha512', 'sha512-crypt', 'ssha512',
               'blf-crypt',
               'PBKDF2',
               'sym-aes-128-cbc',
               'argon2i', 'argon2id'
    ) #not used because missing the encodage HEX, B64 or base64



    US_UID  = fields.String(required=True) #must be unique
    US_NAME  = fields.String(required=True) #Name of the user source
    US_TYPE = fields.String(required=True, validate=validate.OneOf(('ldap', 'sql'))) #Type of the user source

    US_LDAP_HOSTNAME = fields.Url(schemes={'ldap', 'ldaps'}, require_tld=False)
    US_LDAP_BIND_DN      = fields.String() #The bind DN used to authentify against the ldap server
    US_LDAP_BIND_DN_PWD  = fields.String() #The password for the bindDN
    US_LDAP_BASE_DN    = fields.String() #Example: 'dc=example,dc=com'
    US_LDAP_UID        = fields.String(dump_default='uid', load_default='uid') #field with the user's login typically 'uid'
    US_LDAP_CN         = fields.String(dump_default='cn', load_default='cn') #Field that return the Complete Name of the user, typically 'cn'
    US_LDAP_ID         = fields.String(dump_default='uid', load_default='uid') #Field the start the DN
    US_LDAP_SCOPE      = fields.String(dump_default="SUB", load_default="SUB", validate=validate.OneOf(('BASE', 'ONE', 'SUB')))
    US_LDAP_FILTER     = fields.String() #Additional filter for ldap query
    US_LDAP_PWD_POLICY = fields.Boolean(dump_default=False, load_default=False) # set to true if ldap has passwpord policy
    US_LDAP_PWD_UPDATE_SAMBA  = fields.Boolean(dump_default=False, load_default=False) # Also update samba password when changing password
    US_LDAP_QUERY_TIMEOUT = fields.Integer(dump_default=0, load_default=0, validate=validate.Range(min=0)) #Used as parameter by ldap query method. 0 means no limit
    US_LDAP_BIND_AS_USER = fields.Boolean(load_default=False, dump_default=False) #After the fist auth, use the user's DN for the bind DN
    US_LDAP_BIND_FIELD   = fields.List(fields.String())  #Additionnal field to use when doing a bind
    US_LDAP_ATTR_FIELD = fields.List(fields.String(), load_default=['*'], dump_default=['*']) #Attributes ftehc during ldap search queries
    US_LDAP_GROUP_CLASS  = fields.List(fields.String(), load_default=['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'],
                                                     dump_default=['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'])

    US_SQL_USER_URL           = fields.Url(schemes={"mysql", "postgresql"}, require_tld=False) #database uri to the user source
    US_SQL_PREPEND_PWD_SCHEME = fields.Boolean() #should the password be stored in the dabase with the shceme like this {scheme)encryptedValue
    US_SQL_USER_FILTER        = fields.String() #Additional filter to add at the where clause when querying users.
    US_SQL_DOMAIN_FIELD       = fields.String() #Fields where the user's domain is.

    US_MAPPING = fields.Dict() #TODO map sqldap field to Vcard field

    US_CAN_AUTH   = fields.Boolean(required=True) #The users in this US can authenticate
    US_PWD_ALGO   = fields.String() #Algo used to encrypt the user password for login (sql) and when changing password (sql/ldap)
    US_SIM_KEY_TYPE  = fields.String(validate=validate.OneOf(('path', 'env', 'plain')))
    US_SIM_KEY_VALUE = fields.String()
    US_PWD_POLICY       = fields.Boolean(load_default=False, dump_default=False) #Policies on password CAREFUL CONFLICT WITH LDAP_PWD_POLICY
    US_PWD_LEN_MIN = fields.Integer(load_default=4, dump_default=4,validate=validate.Range(min=1)) #Minimum lenght of password
    US_PWD_LEN_MAX = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Maximum lenght of password, 0 means no limit
    US_PWD_UPPERCASE_MIN = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Minimum number of uppercase letter, 0 means no need
    US_PWD_LOWERCASE_MIN = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Minimum number of lowercase letter, 0 means no need
    US_PWD_DIGITS_MIN     = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Minimum number of digits, 0 means no need
    US_PWD_SPECIAL_MIN   = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Minimum number of special char letter, 0 means no need
    US_PWD_SPECIAL_ALLOWED = fields.String(load_default=r'%$&*(){}[]!?\/@#.,:;+=<>-_', dump_default=r'%$&*(){}[]!?\/@#.,:;+=<>-_') #String that contains allowed special character

    US_MAIL                 = fields.List(fields.String(), required=True, dump_default=['mail']) #Names of the sqldap field with the user's mail/alias
    US_MAIL_SERVER_LOGIN    = fields.String() #sqldap field where to fetch the imap login for a user (default to UIDFieldName for ldap or c_uid for sql)
    US_MAIL_FILTERING_LOGIN = fields.String() #sqldap field where to fetch the sieve login for a user (default to UIDFieldName for ldap or c_uid for sql)
    US_MAIL_OUTGOING_LOGIN  = fields.String() #sqldap field where to fecth the smtp login for a user (default to UIDFieldName for ldap or c_uid for sql)

    US_KIND = fields.String() #sqldap field where to check if a user is a resource or not

    US_IS_ADDRESSBOOK = fields.Boolean(required=True) #This US is shown for autocompletion and shared address book
    US_SEARCH = fields.List(fields.String()) #Array of sqldap field used for autocompletion/search of user
    US_DISPLAY_NAME   = fields.String() #Human readable name of this US, will ude US_UID if not set
    US_AUTO_SEARCH    = fields.Boolean(load_default=False, dump_default=False) #Auto return all users of the US whitout typing any char in the search bar.
    US_AUTO_QUERY_LIMIT = fields.Integer(load_default=0, dump_default=0) #Maximum result return for a autocompletion query, default to 0 means no limit.
    US_EXTRA_CONTACT_INFO = fields.String() #TODO add moreflexibility and let the admin tell how it should be shown? sqladp field to show when doing autocompletion (will be "cn <extra> mail")
    US_HIDDEN_USER = fields.List(fields.String()) #List of user to never show to others when searching or autocompletion

    #Resource
    US_HAS_RESOURCE = fields.Boolean(required=True) #Does this user source has resources
    US_RESOURCE_SEARCH = fields.List(fields.String()) #Array of sqldap field used for autocompletion/search of resource
    US_RESOURCE_MULTIBOOKING = fields.String() #sqldap field where to check how much time a resource can be booked simultaneously
    US_RESOURCE_EXTRA_INFO = fields.String() #TODO add moreflexibility and let the admin tell how it should be shwon? sqladp field to show when doing autocompletion (will be "cn <extra> mail")

class UserModuleSettings(SogoSchema):
    """
    Schema for an User module and action
    """

    subparent = "USER_MODULE_SETTINGS"
    dependencies = {
        "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": ("SOGO_D_IDENTITIES_ENABLED", True),
        "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": ("SOGO_D_IDENTITIES_ENABLED", True),
        "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": ("SOGO_D_IDENTITIES_ENABLED", True),

        "SOGO_D_MAIL_JUNK_MAIL_SPAM": ("SOGO_D_MAIL_JUNK_SETTINGS", "mail"),
        "SOGO_D_MAIL_JUNK_MAIL_HAM": ("SOGO_D_MAIL_JUNK_SETTINGS", "mail")
    }
    is_secret = set()

    SOGO_D_MODULE_ACCESS = fields.List(fields.String(), validate=validate.ContainsOnly(('mail', 'calendar', 'contact')),
                                    load_default=['mail', 'calendar', 'contact'],
                                    dump_default=['mail', 'calendar', 'contact'])
    SOGO_D_MAPI_ACCESS = fields.Boolean(load_default=False, dump_default=False) #Allow user to access their data with MAPI
    SOGO_D_EAS_ACCESS = fields.Boolean(load_default=False, dump_default=False) #Allow user to access their data with EAS

    #Folder settings
    SOGO_D_FOLDER_DISABLE_EXPORT           = fields.List(fields.String(), validate=validate.ContainsOnly(('mail', 'calendar', 'contact'))) #Disable or not folder export
    SOGO_D_FOLDER_DISABLE_SHARING          = fields.List(fields.String(), validate=validate.ContainsOnly(('mail', 'calendar', 'contact'))) #Disable or not folder sharing
    SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH = fields.List(fields.String(), validate=validate.ContainsOnly(('mail', 'calendar', 'contact'))) #Disable or not folder sharing to any authenticated user from the domain
    
    SOGO_D_AUTOCOMPLETION_MIN_LEN          = fields.Integer(load_default=2, dump_default=2, validate=validate.Range(min=2)) #Number of (chars needed - 1) to trigger the autocompletion search. At 2 it will trigger for the third char.
                                                                                                                            #TODO make sure that the front wait for a bit before doing the search, like waiting for the user to have ending its typing
    #SOGO_D_API_MAX_REQUEST: max api request a user can make during SOGO_D_API_MAX_REQUEST_INTERVAL second. If limit is reach, it will be block for
    #SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL seconds. SOGO_D_API_MAX_REQUEST = 0 disable any checking.
    #Beware that a user can make many request naturally, only used to block bot/ddos with value of ~100
    SOGO_D_API_MAX_REQUEST                = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0))
    SOGO_D_API_MAX_REQUEST_INTERVAL       = fields.Integer(load_default=30, dump_default=30, validate=validate.Range(min=10))
    SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL = fields.Integer(load_default=300, dump_default=300, validate=validate.Range(min=5))


    #Identities
    SOGO_D_IDENTITIES_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to create identities for their main imap account
    SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to have custom "from" email in their identities
    SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to have custom name  in their identities
    SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to have custom reply-to email in their identities
    SOGO_D_ALLOW_EXT_MAIL_ACCOUNT = fields.Boolean(load_default=False, dump_default=False) #Allow users to create identities for their main imap account


    #Webmail
    SOGO_D_ALLOW_EXT_AVATAR = fields.Boolean(load_default=True, dump_default=True) #Allow users to load external avatar
    SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED = fields.List(fields.Integer(), validate=validate.ContainsOnly((0, 1, 2, 5, 10, 20, 30, 60)),
                                                     load_default=[0, 1, 2, 5, 10, 20, 30, 60],
                                                     dump_default=[0, 1, 2, 5, 10, 20, 30, 60])

    SOGO_D_MAIL_JUNK_SETTINGS = fields.String(validate=validate.OneOf(('None', 'mail'))) #Define a behavior when users set a mail as junk or not junk
    SOGO_D_MAIL_JUNK_MAIL_SPAM = fields.Email() #When set as junk, the og mail is sent to this address
    SOGO_D_MAIL_JUNK_MAIL_HAM = fields.Email() #When set as not junk, the og mail is sent to this address

class MailSettings(SogoSchema):
    """
    Schema for mail settings
    """

    subparent = "MAIL_SETTINGS"
    dependencies = {
        "SOGO_D_IMAP_SERVER": ("SOGO_D_MAIL_SERVER_TYPE", "imap"),
        "SOGO_D_IMAP_PORT": ("SOGO_D_MAIL_SERVER_TYPE", "imap"),
        "SOGO_D_IMAP_ENCRYPTION": ("SOGO_D_MAIL_SERVER_TYPE", "imap"),
        "SOGO_D_IMAP_AUTH_MECH": ("SOGO_D_MAIL_SERVER_TYPE", "imap"),

        "SOGO_D_MAIL_FILTERING_TYPE": ("SOGO_D_MAIL_FILTERING_ENABLED", True),
        "SOGO_D_SIEVE_SERVER": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_PORT": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_ENCRYPTION": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_AUTH_MECH": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_FOLDER_ENCODING": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_HEADER": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_FOOTER": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_SIEVE_FIRST_FILTER": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_VACATION_ENABLED": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_FORWARD_ENABLED": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_FORWARD_ALLOW_USER_DOMAIN": ("SOGO_D_FORWARD_ENABLED", True),
        "SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN": ("SOGO_D_FORWARD_ENABLED", True),
        "SOGO_D_FORWARD_ALLOW_EXT_DOMAIN": ("SOGO_D_FORWARD_ENABLED", True),
        "SOGO_D_FORWARD_WHITELIST": ("SOGO_D_FORWARD_ENABLED", True),
        "SOGO_D_FORWARD_BLACKLIST": ("SOGO_D_FORWARD_ENABLED", True),
        "SOGO_D_NOTIFY_ENABLED": ("SOGO_D_MAIL_FILTERING_TYPE", "sieve"),
        "SOGO_D_NOTIFY_ALLOW_USER_DOMAIN": ("SOGO_D_NOTIFY_ENABLED", True),
        "SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN": ("SOGO_D_NOTIFY_ENABLED", True),
        "SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN": ("SOGO_D_NOTIFY_ENABLED", True),
        "SOGO_D_NOTIFY_WHITELIST": ("SOGO_D_NOTIFY_ENABLED", True),
        "SOGO_D_NOTIFY_BLACKLIST": ("SOGO_D_NOTIFY_ENABLED", True),

        "SOGO_D_SMTP_SERVER": ("SOGO_D_MAIL_OUTGOING_TYPE", "smtp"),
        "SOGO_D_SMTP_PORT": ("SOGO_D_MAIL_OUTGOING_TYPE", "smtp"),
        "SOGO_D_SMTP_ENCRYPTION": ("SOGO_D_MAIL_OUTGOING_TYPE", "smtp"),
        "SOGO_D_SMTP_AUTH_MECH": ("SOGO_D_MAIL_OUTGOING_TYPE", "smtp"),
        "SOGO_D_SMTP_MASTER_ENABLED": ("SOGO_D_MAIL_OUTGOING_TYPE", "smtp"),
        "SOGO_D_SMTP_MASTER_LOGIN": ("SOGO_D_SMTP_MASTER_ENABLED", True),
        "SOGO_D_SMTP_MASTER_PWD": ("SOGO_D_SMTP_MASTER_ENABLED", True),

    }
    is_secret = {"SOGO_D_SMTP_MASTER_PWD",}

    SOGO_D_MAIL_SERVER_TYPE = fields.String(load_default="imap", dump_default="imap", validate=validate.OneOf(('imap',))) #Could be jmap in the future...
    SOGO_D_IMAP_SERVER = fields.String() #Hostname or ip of the imap server
    SOGO_D_IMAP_PORT = fields.Integer(load_default=143, dump_default=143, validate=validate.Range(min=1, max=65535))
    SOGO_D_IMAP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'TLS', 'SSL')))
    SOGO_D_IMAP_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'plain', 'xoauth2')))
    SOGO_D_SOFT_EMAIL_QUOTA = fields.Integer(load_default=1, dump_default=1, validate=validate.Range(min=0, max=1, min_inclusive=False)) #Multiplier to the true quota for the user
    SOGO_D_MAIL_PURGE_ALLOW     = fields.Boolean(load_default=True, dump_default=True) #Allow user to purger their folder (delete all before a date)
    SOGO_D_MAIL_PURGE_MIN_DATE  = fields.Integer(load_default=0, dump_default=0) #Minimum age in days that a user can purge their mail (0 means they can purge everything)

    SOGO_D_MAIL_FILTERING_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set autoreply sieve rule
    SOGO_D_MAIL_FILTERING_TYPE = fields.String(load_default="sieve", dump_default="sieve", validate=validate.OneOf(('sieve',))) #For sendmail, look at SOGO_S_SENDMAIL
    SOGO_D_SIEVE_SERVER = fields.String() #Hostname or ip of the sieve server
    SOGO_D_SIEVE_PORT = fields.Integer(load_default=4190 , dump_default=4190 , validate=validate.Range(min=1, max=65535))
    SOGO_D_SIEVE_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'TLS', 'SSL')))
    SOGO_D_SIEVE_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'plain', 'xoauth2')))
    SOGO_D_SIEVE_FOLDER_ENCODING = fields.String(load_default="utf-7", dump_default="utf-7", validate=validate.OneOf(('utf-7', 'utf-8')))
    SOGO_D_SIEVE_HEADER = fields.String() #Sieve script that will be set for each user sieve script at the top level
    SOGO_D_SIEVE_FOOTER = fields.String() #Sieve script that will be set for each user sieve script at the bottom level
    SOGO_D_SIEVE_FIRST_FILTER = fields.String() #Sieve script that will set for new users
    SOGO_D_VACATION_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set autoreply sieve rule
    SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS = fields.Boolean(load_default=False, dump_default=False) #Allow users to set a zero day for vacation message (meaning it always auroreply)
    SOGO_D_FORWARD_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule
    SOGO_D_FORWARD_ALLOW_USER_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule towards its own domain
    SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule towards other sogo's domains
    SOGO_D_FORWARD_ALLOW_EXT_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule towards external domains
    SOGO_D_FORWARD_WHITELIST = fields.List(fields.String()) #Whitelist for forward sieve rule
    SOGO_D_FORWARD_BLACKLIST = fields.List(fields.String()) #Blacklist for forward sieve rule
    SOGO_D_NOTIFY_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule
    SOGO_D_NOTIFY_ALLOW_USER_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule towards its own domain
    SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule towards other sogo's domains
    SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule towards external domains
    SOGO_D_NOTIFY_WHITELIST = fields.List(fields.String()) #Whitelist for notify sieve rule
    SOGO_D_NOTIFY_BLACKLIST = fields.List(fields.String()) #Blacklist for notify sieve rule


    SOGO_D_MAIL_OUTGOING_TYPE = fields.String(load_default="smtp", dump_default="smtp", validate=validate.OneOf(('smtp', 'sendmail'))) #For sendmail, look at SOGO_S_SENDMAIL
    SOGO_D_SMTP_SERVER = fields.String() #Hostname or ip of the smtp server
    SOGO_D_SMTP_PORT = fields.Integer(load_default=587, dump_default=584, validate=validate.Range(min=1, max=65535))
    SOGO_D_SMTP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'TLS', 'SSL')))
    SOGO_D_SMTP_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'plain', 'xoauth2')))
    SOGO_D_SMTP_MASTER_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Use a master account for system message (notif, event) instead of using the user account
    SOGO_D_SMTP_MASTER_LOGIN = fields.String()
    SOGO_D_SMTP_MASTER_PWD = fields.String()
    #Mailing -> Settings should be defined by the smtp server. But theyr are here to avoid making a smtp requets and reflect its rules.
    #SOGO_D_MAIL_MAX_SUBMISSION: max mail a user can send during SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL second. If limit is reach, it will be block for
    #SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl seconds. SOGO_D_MAIL_MAX_SUBMISSION = 0 disable any checking.
    SOGO_D_MAIL_MAX_SUBMISSION                = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0))
    SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL       = fields.Integer(load_default=30, dump_default=30, validate=validate.Range(min=10))
    SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl = fields.Integer(load_default=300, dump_default=300, validate=validate.Range(min=5))
    #TODO: for this kind of case, add a param to define exempt uid? For exemple a ressource room that could send a lot of mail...
    SOGO_D_MAIL_MAX_RECIPIENT = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #0 means no limit
    SOGO_D_MAIL_SYSTEM_FROM = fields.Email() #Custom from used for system message (password recovery for now)

class CalendarContactSettings(SogoSchema):
    """
    Schema for calendar and contact settings
    """

    subparent = "CALENDAR_CONTACT_SETTINGS"
    dependencies = {
        "SOGO_D_CALDAV_START_TIME": ("SOGO_D_CALDAV_ENABLED", True),
        "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": ("SOGO_D_CALDAV_ENABLED", True),

        "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": ("SOGO_D_CARDAV_ENABLED", True),

        "SOGO_D_JITSI_BASE_URL": ("SOGO_D_JITSI_LINK_ENABLED", True),

    }
    is_secret = set()

    SOGO_D_CALDAV_ENABLED = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE = fields.Boolean(load_default=False, dump_default=False) #Enable or not public caldav access
    SOGO_D_CALDAV_START_TIME  = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #limit the the span of time of the events return in a caldav request
                                                                                                               #0 means no limit, 180 means only events that are less than 180 days olds are returned.
    
    SOGO_D_CARDAV_ENABLED  = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE = fields.Boolean(load_default=False, dump_default=False) #Enable or not public cardav access

    SOGO_D_JITSI_LINK_ENABLED = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_JITSI_BASE_URL     = fields.Url(schemes={'http','https'})

    SOGO_D_REMINDER_ALLOW_MAIL = fields.Boolean(load_default=True, dump_default=True) #Allow user to set reminder sent by email for events/tasks
