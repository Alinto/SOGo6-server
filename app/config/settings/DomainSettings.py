from __future__ import annotations
from typing import TYPE_CHECKING, Type

from marshmallow import fields, validate

from app.config.settings.SogoSchema import SogoSchema
from app.utils import errors as err
from app.utils import constants as cs
from app.utils.config.generateObjFromSchema import SettingsObj
from app.utils.db.Condition import string_filter_to_conditions
from app.utils.exceptions import AggravatedException
from app.utils.strings import parse_url_str

if TYPE_CHECKING:
    from app.utils.db.Condition import Condition

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
        "SOGO_D_OPENID_FETCH_USER_PROFILE": ("SOGO_D_AUTH_TYPE", "openid"),
        "SOGO_D_OPENID_ALLOW_REDIRECT": ("SOGO_D_AUTH_TYPE", "openid"),

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
    is_required = {"SOGO_D_OPENID_CLIENT_NAME", "SOGO_D_OPENID_CLIENT_SECRET", "SOGO_D_OPENID_ALLOW_REDIRECT"}
    is_needed_by_ui = {"SOGO_D_PWD_CHANGE_ENABLED", "SOGO_D_PWD_RECOVERY",
                       "SOGO_D_PWD_RECOVERY_METHOD", "SOGO_D_LOGIN_MFA",
                        "SOGO_D_LOGIN_MFA_METHOD"}

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
    SOGO_D_OPENID_TOKEN_CHECK_INTERVAL = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #Interval where a valid token is not checked again. 0 means always checked.
    SOGO_D_OPENID_REFRESH_ENABLE       = fields.Boolean(load_default=True, dump_default=True) # Allowed or not sogo to refresh token if the openid server has the mechanism
    SOGO_D_OPENID_ENDSESSION_ENABLED   = fields.Boolean(load_default=False, dump_default=False) # Allowed or not sogo to logout from the openid server instead of just the webmail
    SOGO_D_OPENID_FETCH_USER_PROFILE   = fields.Boolean(load_default=True, dump_default=True) # sogo will fetch the user profile to get the user's email. If no, directly fetch from the token.
    SOGO_D_OPENID_ALLOW_REDIRECT       = fields.List(fields.Url()) #List of UI redirect link that are allowed after the obtention of access_token. See openid flow pdf.

    #IF SOGO_D_AUTH_TYPE = 'saml2'
    SOGO_D_SAML2_URL  = fields.Url(schemes={'http','https'}, require_tld=False) #TODO saml2 configuration....

    #If SOGO_D_AUTH_TYPE = 'plain'
    SOGO_D_PWD_CHANGE_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to change the password (for ldap it means the ldap admin account is allow to do that too)
    #SOGO_D_LOGIN_CHECK_MAX_ATTEMPT: max login attept a user can make during SOGO_D_LOGIN_CHECK_TIME_SPAN second. If limit is reach, it will be block for
    #SOGO_D_LOGIN_CHECK_BLOCK_TIME seconds. SOGO_D_LOGIN_CHECK_MAX_ATTEMPT = 0 disable any checking.
    SOGO_D_LOGIN_CHECK_MAX_ATTEMPT = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Number of failed attempt during SOGO_D_LOGIN_CHECK_TIME_SPAN before blocking
    SOGO_D_LOGIN_CHECK_TIME_SPAN   = fields.Integer(load_default=600, dump_default=600,validate=validate.Range(min=5)) #Time span when user can do SOGO_D_LOGIN_CHECK_MAX_ATTEMPT failed login attempt
    SOGO_D_LOGIN_CHECK_BLOCK_TIME  = fields.Integer(load_default=300, dump_default=300,validate=validate.Range(min=5)) #Time span where a user is forbidden to login after too many fail attempt.

    SOGO_D_PWD_RECOVERY = fields.Boolean(load_default=True, dump_default=True) #Enable or not users to set a method for password recovery
    SOGO_D_PWD_RECOVERY_METHOD = fields.List(fields.String(), validate=validate.ContainsOnly(('secretQuestion', 'secondaryEmail', 'apiCall')))
    SOGO_D_PWD_RECOVERY_FORCE = fields.Boolean(load_default=False, dump_default=False) #Force users to set a recovery method, overwrite SOGO_D_PWD_RECOVERY
    SOGO_D_PWD_RECOVERY_DELAY = fields.Integer(load_default=86400, dump_default=86400,validate=validate.Range(min=0)) #Delay in seconds before the user can ask again for a password recovery, 0 means there's no limit
    SOGO_D_LOGIN_MFA = fields.Boolean(load_default=True, dump_default=True) #Enable or not users to set a MFA method for password
    SOGO_D_LOGIN_MFA_METHOD = fields.List(fields.String(), validate=validate.ContainsOnly(('totp',)))
    SOGO_D_LOGIN_MFA_FORCE = fields.Boolean(load_default=False, dump_default=False) #Force users to set a recovery method, overwrite SOGO_D_PWD_RECOVERY

class AuthSettingsObj(SettingsObj):
    """
    Obj with the fields of schema AuthSettings as attributes with the proper type.
    """

    SOGO_D_AUTH_TYPE: str = "plain"
    SOGO_D_CAS_URL: str = ""
    SOGO_D_CAS_LOGOUT_ENABLED: bool = False
    SOGO_D_OPENID_CONFIG_URL: str = ""
    SOGO_D_OPENID_CLIENT_NAME: str = ""
    SOGO_D_OPENID_CLIENT_SECRET: str = ""
    SOGO_D_OPENID_SCOPE: str = 'openid profile email'
    SOGO_D_OPENID_EMAIL: str = "email"
    SOGO_D_OPENID_TOKEN_CHECK_INTERVAL: int = 0
    SOGO_D_OPENID_REFRESH_ENABLE: bool = True
    SOGO_D_OPENID_ENDSESSION_ENABLED: bool = False
    SOGO_D_OPENID_FETCH_USER_PROFILE: bool = True
    SOGO_D_OPENID_ALLOW_REDIRECT: list[str] = []
    SOGO_D_SAML2_URL: str = ""
    SOGO_D_PWD_CHANGE_ENABLED: bool = False
    SOGO_D_LOGIN_CHECK_MAX_ATTEMPT: int = 0
    SOGO_D_LOGIN_CHECK_TIME_SPAN: int = 600
    SOGO_D_LOGIN_CHECK_BLOCK_TIME: int = 300
    SOGO_D_PWD_RECOVERY: bool = True
    SOGO_D_PWD_RECOVERY_METHOD: list[str] = []
    SOGO_D_PWD_RECOVERY_FORCE: bool = False
    SOGO_D_PWD_RECOVERY_DELAY: int = 86400
    SOGO_D_LOGIN_MFA: bool = True
    SOGO_D_LOGIN_MFA_METHOD: list[str] = []
    SOGO_D_LOGIN_MFA_FORCE: bool = False


class UserSourceSettings(SogoSchema):
    """
    Schema for an agnostic User Source
    """

    subparent = "USER_SOURCE"
    is_duplicable = True
    is_uid = "US_UID"
    dependencies = {
        "US_LDAP_HOSTNAME": ("US_TYPE", "ldap"),
        "US_LDAP_PORT": ("US_TYPE", "ldap"),
        "US_LDAP_ENCRYPTION": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_DN": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_DN_PWD": ("US_TYPE", "ldap"),
        "US_LDAP_BASE_DN": ("US_TYPE", "ldap"),
        "US_LDAP_BASE_DN_USE_TLD": ("US_TYPE", "ldap"),
        "US_LDAP_ID": ("US_TYPE", "ldap"),
        "US_LDAP_SCOPE": ("US_TYPE", "ldap"),
        "US_LDAP_PWD_POLICY": ("US_TYPE", "ldap"),
        "US_LDAP_PWD_UPDATE_SAMBA": ("US_TYPE", "ldap"),
        "US_LDAP_QUERY_TIMEOUT": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_AS_USER": ("US_TYPE", "ldap"),
        "US_LDAP_BIND_FIELD": ("US_TYPE", "ldap"),
        "US_LDAP_ATTR_FIELD": ("US_TYPE", "ldap"),
        "US_LDAP_GROUP_CLASS": ("US_TYPE", "ldap"),

        "US_DB_TYPE": ("US_TYPE", "sql"),
        "US_DB_NAME": ("US_TYPE", "sql"),
        "US_DB_USER": ("US_TYPE", "sql"),
        "US_DB_PASS": ("US_TYPE", "sql"),
        "US_DB_HOST": ("US_TYPE", "sql"),
        "US_DB_PORT": ("US_TYPE", "sql"),
        "US_DB_ENCRYPTION": ("US_TYPE", "sql"),
        "US_DB_ENCODAGE": ("US_TYPE", "sql"),
        "US_DB_FIELD_PWD": ("US_TYPE", "sql"),
        "US_DB_PREPEND_PWD_SCHEME": ("US_TYPE", "sql"),
        "US_DB_FIELD_DOMAIN": ("US_TYPE", "sql"),
        "US_DB_PWD_POLICY": ("US_CAN_AUTH", True),
        "US_DB_PWD_LEN_MIN": ("US_DB_PWD_POLICY", True),
        "US_DB_PWD_LEN_MAX": ("US_DB_PWD_POLICY", True),
        "US_DB_PWD_UPPERCASE_MIN": ("US_DB_PWD_POLICY", True),
        "US_DB_PWD_LOWERCASE_MIN": ("US_DB_PWD_POLICY", True),
        "US_DB_PWD_DIGITS_MIN": ("US_DB_PWD_POLICY", True),
        "US_DB_PWD_SPECIAL_MIN": ("US_DB_PWD_POLICY", True),
        "US_DB_PWD_SPECIAL_ALLOWED": ("US_DB_PWD_POLICY", True),


        "US_PWD_ALGO": ("US_CAN_AUTH", True),
        "US_SIM_KEY_TYPE": ("US_PWD_ALGO", 'sym-aes-128-cbc'),
        "US_SIM_KEY_VALUE": ("US_PWD_ALGO", 'sym-aes-128-cbc'),

        "US_MAIL": ("US_CAN_AUTH", True),
        "US_MAIL_SERVER_LOGIN": ("US_CAN_AUTH", True),
        "US_MAIL_FILTERING_LOGIN": ("US_CAN_AUTH", True),
        "US_MAIL_OUTGOING_LOGIN": ("US_CAN_AUTH", True),

        "US_SEARCH": ("US_IS_ADDRESSBOOK", True),
        "US_DISPLAY_NAME": ("US_IS_ADDRESSBOOK", True),
        "US_AUTO_SEARCH": ("US_IS_ADDRESSBOOK", True),
        "US_EXTRA_CONTACT_INFO": ("US_IS_ADDRESSBOOK", True),
        "US_HIDDEN_USER": ("US_IS_ADDRESSBOOK", True),

        "US_RESOURCE_SEARCH": ("US_HAS_RESOURCE", True),
        "US_RESOURCE_MULTIBOOKING": ("US_HAS_RESOURCE", True),
        "US_RESOURCE_EXTRA_INFO": ("US_HAS_RESOURCE", True),
    }
    is_required = {"US_LDAP_HOSTNAME", "US_LDAP_BIND_DN", "US_LDAP_BIND_DN_PWD",
                   "US_LDAP_BASE_DN", "US_LDAP_ID",
                   "US_SQL_USER_URL", "US_DB_PREPEND_PWD_SCHEME"}

    is_secret = {"US_LDAP_BIND_DN_PWD",}
    is_needed_by_ui = {"US_DB_PWD_POLICY", "US_DB_PWD_LEN_MIN",
                    "US_DB_PWD_LEN_MAX", "US_DB_PWD_UPPERCASE_MIN",
                    "US_DB_PWD_LOWERCASE_MIN", "US_DB_PWD_DIGITS_MIN",
                    "US_DB_PWD_SPECIAL_MIN", "US_DB_PWD_SPECIAL_ALLOWED",
                    "US_AUTO_SEARCH"}

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



    US_UID  = fields.String(required=True) #must be unique and cannot be change afterwards
    US_NAME  = fields.String(required=True) #Name of the user source
    US_DESCRIPTION = fields.String() #Description of tise user source
    US_TYPE = fields.String(required=True, validate=validate.OneOf(('ldap', 'db'))) #Type of the user source

    #LDAP params
    US_LDAP_HOSTNAME = fields.String() #Hostname or ip of the ldap server
    US_LDAP_PORT = fields.Integer(load_default=390, dump_default=390, validate=validate.Range(min=1, max=65535))
    US_LDAP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(cs.SOCK_ENC_LIST))
    US_LDAP_BIND_DN      = fields.String() #The bind DN used to authentify against the ldap server
    US_LDAP_BIND_DN_PWD  = fields.String() #The password for the bindDN
    US_LDAP_BASE_DN    = fields.String() #Example: 'dc=example,dc=com'
    US_LDAP_BASE_DN_USE_TLD = fields.Boolean(dump_default=True, load_default=True) #When using the wildcard %d in the base DN, tell if the TLD (Top Level Domain)
                                                    #E.g. US_LDAP_BASE_DN="ou=%d,dc=example,dc=org", for user sogo@sogo.nu
                                                    #US_LDAP_BASE_DN_USE_TLD=True -> BASE_DN="ou=sogo.nu,dc=example,dc=org"
                                                    #US_LDAP_BASE_DN_USE_TLD=False -> BASE_DN="ou=sogo,dc=example,dc=org"
    US_LDAP_ID         = fields.String(dump_default='uid', load_default='uid') #Field the start the DN
    US_LDAP_SCOPE      = fields.String(dump_default=cs.LDAP_SCOPE_SUB, load_default=cs.LDAP_SCOPE_SUB,
                                       validate=validate.OneOf((cs.LDAP_SCOPE_BASE, cs.LDAP_SCOPE_ONE, cs.LDAP_SCOPE_SUB)))
    US_LDAP_PWD_POLICY = fields.Boolean(dump_default=False, load_default=False) # set to true if ldap has passwpord policy https://datatracker.ietf.org/doc/html/rfc3062
    US_LDAP_PWD_UPDATE_SAMBA  = fields.Boolean(dump_default=False, load_default=False) # Also update samba password when changing password
    US_LDAP_QUERY_TIMEOUT = fields.Integer(dump_default=0, load_default=0, validate=validate.Range(min=0)) #Used as parameter by ldap query method. 0 means no limit
    US_LDAP_BIND_AS_USER = fields.Boolean(load_default=False, dump_default=False) #Use user's DN to make bind before search query instead of US_LDAP_BIND_DN
    US_LDAP_BIND_FIELD   = fields.List(fields.String())  #Info to fetch the correct DN of a user
    US_LDAP_ATTR_FIELD = fields.List(fields.String(), load_default=['*'], dump_default=['*']) #Attributes fetch during ldap search queries
    US_LDAP_GROUP_CLASS  = fields.List(fields.String(), load_default=['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'],
                                                     dump_default=['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'])
    #DB PARAM
    US_DB_TYPE = fields.String(validate=validate.OneOf(("mysql", "postgresql")))
    US_DB_NAME = fields.String()
    US_DB_USER = fields.String()
    US_DB_PASS = fields.String()
    US_DB_HOST = fields.String()
    US_DB_PORT = fields.Integer()
    US_DB_ENCRYPTION = fields.Boolean(load_default=False, dump_default=False)
    US_DB_ENCODAGE = fields.String(dump_default='utf8', load_default='utf8')
    US_DB_FIELD_PWD            = fields.String(dump_default='c_password', load_default='c_password') # Name of the column with the user password
    US_DB_PREPEND_PWD_SCHEME = fields.Boolean(load_default=False, dump_default=False) #IS the password stored in the db with the shceme like this '{scheme)encryptedValue'
    US_DB_FIELD_DOMAIN       = fields.String() #Fields where the user's domain is.
    US_DB_PWD_POLICY       = fields.Boolean(load_default=False, dump_default=False) #Policies on password CAREFUL CONFLICT WITH LDAP_PWD_POLICY
    US_DB_PWD_LEN_MIN = fields.Integer(load_default=4, dump_default=4,validate=validate.Range(min=1)) #Minimum lenght of password
    US_DB_PWD_LEN_MAX = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Maximum lenght of password, 0 means no limit
    US_DB_PWD_UPPERCASE_MIN = fields.Integer(load_default=-1, dump_default=-1,validate=validate.Range(min=-1)) #Minimum number of uppercase letter, 0 means no need
    US_DB_PWD_LOWERCASE_MIN = fields.Integer(load_default=-1, dump_default=-1,validate=validate.Range(min=-1)) #Minimum number of lowercase letter, 0 means no need
    US_DB_PWD_DIGITS_MIN     = fields.Integer(load_default=-1, dump_default=-1,validate=validate.Range(min=-1)) #Minimum number of digits, 0 means no need
    US_DB_PWD_SPECIAL_MIN   = fields.Integer(load_default=-1, dump_default=-1,validate=validate.Range(min=-1)) #Minimum number of special char letter, 0 means no need
    US_DB_PWD_SPECIAL_ALLOWED = fields.String(load_default=r'%$&*(){}[]!?\/@#.,:;+=<>-_', dump_default=r'%$&*(){}[]!?\/@#.,:;+=<>-_') #String that contains allowed special character


    #COMMON PARAM
    US_FIELD_UID = fields.String(dump_default='uid', load_default='uid') #field with the user's login typically 'uid' or 'c_uid' but can be 'email'
    US_FIELD_CN = fields.String(dump_default='cn', load_default='cn') #Field that return the Complete Name of the user, typically 'cn' for ldap or 'c_cn' bor db
    US_MAIL                 = fields.List(fields.String(), required=True, dump_default=['mail']) #Names of the sqldap field with the user's mail/alias
    US_MAIL_SERVER_LOGIN    = fields.String() #sqldap field where to fetch the imap login for a user (default to UIDFieldName for ldap or c_uid for sql)
    US_MAIL_FILTERING_LOGIN = fields.String() #sqldap field where to fetch the sieve login for a user (default to UIDFieldName for ldap or c_uid for sql)
    US_MAIL_OUTGOING_LOGIN  = fields.String() #sqldap field where to fecth the smtp login for a user (default to UIDFieldName for ldap or c_uid for sql)
    US_MAPPING = fields.Dict() #TODO map sqldap field to Vcard field
    US_FILTER = fields.String() #Additional filter for user source query (ex: `"active" == 1`)

    US_IMAP_HOST_FIELDNAME = fields.String() #sqldap field where the imap hostname is stored for a user (LEGACY - DEPRECATED)

    US_CAN_AUTH   = fields.Boolean(required=True) #The users in this US can authenticate
    US_PWD_ALGO   = fields.String() #Algo used to encrypt the user password for login (sql) and when changing password (sql and ldap without password policy or AD)
    US_SIM_KEY_TYPE  = fields.String(validate=validate.OneOf(('path', 'env', 'plain')))
    US_SIM_KEY_VALUE = fields.String()


    US_FIELD_KIND = fields.String() #sqldap field where to check if a user is a resource or not
    US_MODULE_ACCESS = fields.Dict(fields.String(validate=validate.OneOf(('Calendar', 'Mail', 'Contact'))),
                                   fields.Dict()) # Module constraints. E.g. {"Calendars": {"c_calendar_disable": True}} means that all users that
                                                  # have the sqldap field c_calendar_disable set at True, it doens't have Calendar access.

    #Seach/autocompletion
    US_IS_ADDRESSBOOK = fields.Boolean(required=True) #This US is shown for autocompletion and shared address book
    US_DISPLAY_NAME   = fields.String() #Human readable name of this US, will ude US_UID if not set. Fallback to US_NAME if not set
    US_SEARCH = fields.List(fields.String()) #Array of sqldap field used for autocompletion/search of user
    US_AUTO_SEARCH    = fields.Boolean(load_default=False, dump_default=False) #Auto return all users of the US whitout typing any char in the search bar.
    US_EXTRA_CONTACT_INFO = fields.String() #TODO add moreflexibility and let the admin tell how it should be shown? sqladp field to show when doing autocompletion (will be "cn <extra> mail")
    US_HIDDEN_USER = fields.List(fields.String()) #List of user's uid to never show to others when searching or autocompletion ex: noreply@sogo.nu
    US_DOMAIN_PARTITION = fields.Boolean(load_default=False, dump_default=False) #If true, User can only see users from the same domain.
    US_DOMAIN_VISIBLE = fields.List(fields.String()) #If US_DOMAIN_PARTITION == True, add domains that will still be see by all
                                            #"ALL" -> all domains, "sogo.nu" -> sogo.nu is visible by all, "!sogo.nu", sogo is visible for no on (to be used wih ALL))

    #Resource
    US_HAS_RESOURCE = fields.Boolean(required=True) #Does this user source has resources
    US_RESOURCE_SEARCH = fields.List(fields.String()) #Array of sqldap field used for autocompletion/search of resource
    US_RESOURCE_MULTIBOOKING = fields.String() #sqldap field where to check how much time a resource can be booked simultaneously
    US_RESOURCE_EXTRA_INFO = fields.String() #TODO add moreflexibility and let the admin tell how it should be shwon? sqladp field to show when doing autocompletion (will be "cn <extra> mail")

class UserSourceSettingsObj(SettingsObj):
    """
    Obj with the fields of schema UserSourceSettings as attributes with the proper type.
    """

    US_UID: str = ""
    US_NAME: str = ""
    US_DESCRIPTION: str = ""
    US_TYPE: str = ""

    US_LDAP_HOSTNAME: str = ""
    US_LDAP_PORT: int = 390
    US_LDAP_ENCRYPTION: str = "None"
    US_LDAP_BIND_DN: str = ""
    US_LDAP_BIND_DN_PWD: str = ""
    US_LDAP_BASE_DN: str = ""
    US_LDAP_BASE_DN_USE_TLD: bool = True
    US_LDAP_ID: str = "uid"
    US_LDAP_SCOPE: str = cs.LDAP_SCOPE_SUB
    US_LDAP_PWD_POLICY: bool = False
    US_LDAP_PWD_UPDATE_SAMBA: bool = False
    US_LDAP_QUERY_TIMEOUT: int = 0
    US_LDAP_BIND_AS_USER: bool = False
    US_LDAP_BIND_FIELD: list[str] = []
    US_LDAP_ATTR_FIELD: list[str] = ['*']
    US_LDAP_GROUP_CLASS: list[str] = ['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup']

    US_FIELD_UID: str = 'uid'
    US_FIELD_CN: str = 'cn'
    US_FIELD_EMAIL: str = 'mail'
    US_MAPPING: dict = {}
    US_CAN_AUTH: bool = False
    US_PWD_ALGO: str = ""
    US_SIM_KEY_TYPE: str = ""
    US_SIM_KEY_VALUE: str = ""

    US_DB_TYPE: str = "postgresql"
    US_DB_NAME: str = ""
    US_DB_USER: str = ""
    US_DB_PASS: str = ""
    US_DB_HOST: str = ""
    US_DB_PORT: int = 5432
    US_DB_ENCRYPTION: bool = False
    US_DB_ENCODAGE: str = 'utf8'
    US_DB_FIELD_PWD: str = 'c_password'
    US_DB_PREPEND_PWD_SCHEME: bool = False
    US_DB_FIELD_DOMAIN: str  = ""
    US_DB_PWD_POLICY: bool = False
    US_DB_PWD_LEN_MIN: int = 4
    US_DB_PWD_LEN_MAX: int = 0
    US_DB_PWD_UPPERCASE_MIN: int = -1
    US_DB_PWD_LOWERCASE_MIN: int = -1
    US_DB_PWD_DIGITS_MIN: int = -1
    US_DB_PWD_SPECIAL_MIN: int = -1
    US_DB_PWD_SPECIAL_ALLOWED: str = r"%$&*(){}[]!?\/@#.,:;+=<>-_"


    US_MAIL: list[str] = ['mail']
    US_MAIL_SERVER_LOGIN: str = ""
    US_MAIL_FILTERING_LOGIN: str = ""
    US_MAIL_OUTGOING_LOGIN: str = ""
    US_IMAP_HOST_FIELDNAME: str = ""
    US_MODULE_ACCESS: dict[str, dict] = {}
    US_FILTER: str = ""
    US_FIELD_KIND: str = ""
    US_IS_ADDRESSBOOK: bool = False
    US_SEARCH: list[str] = []
    US_DISPLAY_NAME: str = ""
    US_AUTO_SEARCH: bool = False
    US_EXTRA_CONTACT_INFO: str = ""
    US_HIDDEN_USER: list[str] = []
    US_HAS_RESOURCE: bool = False
    US_RESOURCE_SEARCH: list[str] = []
    US_RESOURCE_MULTIBOOKING: str = ""
    US_RESOURCE_EXTRA_INFO: str = ""

    def get_user_source_settings(self, type_us:str) -> dict:
        """
        Returns the parameters needed for the user source's client class init

        :param type_us: Type of the user source, must matcv US_TYPE possible value.
        :type type_us: str
        :return: The dictonnary ready to be passes as kwargs to the class init
        :rtype: dict
        """

        if type_us == "ldap":
            #Must match ClientLdap __init__ param
            ldap_filer: Condition|None = None
            if self.US_FILTER:
                ldap_filer = string_filter_to_conditions(self.US_FILTER)

            return {
                    "ldap_host": self.US_LDAP_HOSTNAME,
                    "ldap_port": self.US_LDAP_PORT,
                    "ldap_enc": self.US_LDAP_ENCRYPTION,
                    "ldap_bind_dn": self.US_LDAP_BIND_DN,
                    "ldap_bind_pwd": self.US_LDAP_BIND_DN_PWD,
                    "ldap_base_dn": self.US_LDAP_BASE_DN,
                    "ldap_scope": self.US_LDAP_SCOPE,
                    "ldap_uid": self.US_FIELD_UID,
                    "ldap_id": self.US_LDAP_ID,
                    "ldap_cn": self.US_FIELD_CN,
                    "ldap_mails": self.US_MAIL,
                    "ldap_bind_fields": self.US_LDAP_BIND_FIELD,
                    "ldap_bind_as_user": self.US_LDAP_BIND_AS_USER,
                    "ldap_pwd_policy": self.US_LDAP_PWD_POLICY,
                    "ldap_filter": ldap_filer,
                    # self.US_LDAP_PWD_UPDATE_SAMBA,
                    # self.US_LDAP_QUERY_TIMEOUT,
                    # self.US_LDAP_ATTR_FIELD,
                    # self.US_LDAP_GROUP_CLASS
            }
        elif type_us == "db":
            #Transform url to parameters
            parsed_url = parse_url_str(self.US_SQL_USER_URL)
            encodage = "utf8"
            
            if type_us == "mysql":
                encodage = parsed_url["params"].get("charset", "utf8")
            elif type_us == "postgresql":
                encodage = parsed_url["params"].get("client_encoding", "utf8")

            MAP_KEY_CLASS = {
                "mysql": "ClientMySQL",
                "postgresql": "ClientPostgreSQL"
            }

            return {
                "db_type": MAP_KEY_CLASS[type_us],
                "db_param": {
                    "db_user": parsed_url["usernname"],
                    "db_pwd":  parsed_url["password"],
                    "db_host": parsed_url["hostname"],
                    "db_port": parsed_url["port"],
                    "db_ssl":  "", #TODO get ssl from url string
                    "db_enc":  encodage
                }
            }
        else:
            raise AggravatedException(err.ERROR_CONFIG_WRONG_US_SERVER.m, err.ERROR_CONFIG_WRONG_US_SERVER)


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
    is_needed_by_ui = {"SOGO_D_MODULE_ACCESS", "SOGO_D_FOLDER_DISABLE_EXPORT",
                       "SOGO_D_FOLDER_DISABLE_SHARING", "SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH",
                       "SOGO_D_AUTOCOMPLETION_MIN_LEN", "SOGO_D_IDENTITIES_ENABLED",
                       "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED", "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED",
                       "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED", "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT", "SOGO_D_ALLOW_EXT_AVATAR"}

    SOGO_D_MODULE_ACCESS = fields.List(fields.String(), validate=validate.ContainsOnly(('mail', 'calendar', 'contact')),
                                    load_default=['mail', 'calendar', 'contact'],
                                    dump_default=['mail', 'calendar', 'contact'])
    SOGO_D_EAS_ACCESS = fields.Boolean(load_default=False, dump_default=False) #Allow user to access their data with EAS

    #Folder settings
    SOGO_D_FOLDER_DISABLE_EXPORT           = fields.List(fields.String(), load_default=['mail', 'calendar', 'contact'],
                                                         dump_default=['mail', 'calendar', 'contact'],
                                                         validate=validate.ContainsOnly(('mail', 'calendar', 'contact'))) #Disable or not folder export
    SOGO_D_FOLDER_DISABLE_SHARING          = fields.List(fields.String(), load_default=['mail', 'calendar', 'contact'],
                                                         dump_default=['mail', 'calendar', 'contact'],
                                                         validate=validate.ContainsOnly(('mail', 'calendar', 'contact'))) #Disable or not folder sharing
    SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH = fields.List(fields.String(), load_default=['mail', 'calendar', 'contact'],
                                                         dump_default=['mail', 'calendar', 'contact'],
                                                         validate=validate.ContainsOnly(('mail', 'calendar', 'contact'))) #Disable or not folder sharing to any authenticated user from the domain
    
    SOGO_D_AUTOCOMPLETION_MIN_LEN          = fields.Integer(load_default=3, dump_default=3, validate=validate.Range(min=2)) #Number of chars needed to trigger the autocompletion search. At 3 it will trigger for the third char.
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
    SOGO_D_ALLOW_EXT_MAIL_ACCOUNT = fields.Boolean(load_default=False, dump_default=False) #Allow users to add external mail accounts
    SOGO_D_SIGNATURE_SIZE_LIMIT = fields.Integer(load_default=200, dump_default=200, validate=validate.Range(min=0)) #Max size of a signature in KB (kilobytes). 0 means no limit. Default: 200 KB

    #Webmail
    SOGO_D_ALLOW_EXT_AVATAR = fields.Boolean(load_default=True, dump_default=True) #Allow users to load external avatar

    SOGO_D_MAIL_JUNK_SETTINGS = fields.String(validate=validate.OneOf(('None', 'mail'))) #Define a behavior when users set a mail as junk or not junk
    SOGO_D_MAIL_JUNK_MAIL_SPAM = fields.Email() #When set as junk, the og mail is sent to this address
    SOGO_D_MAIL_JUNK_MAIL_HAM = fields.Email() #When set as not junk, the og mail is sent to this address

class UserModuleSettingsObj(SettingsObj):
    """
    Obj with the fields of schema UserModuleSettings as attributes with the proper type.
    """

    SOGO_D_MODULE_ACCESS: list[str] = ['mail', 'calendar', 'contact']
    SOGO_D_EAS_ACCESS: bool = False
    SOGO_D_FOLDER_DISABLE_EXPORT: list[str] = []
    SOGO_D_FOLDER_DISABLE_SHARING: list[str] = []
    SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH: list[str] = []
    SOGO_D_AUTOCOMPLETION_MIN_LEN: int = 2
    SOGO_D_API_MAX_REQUEST: int = 0
    SOGO_D_API_MAX_REQUEST_INTERVAL: int = 30
    SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL: int = 300
    SOGO_D_IDENTITIES_ENABLED: bool = False
    SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED: bool = False
    SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED: bool = False
    SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED: bool = False
    SOGO_D_ALLOW_EXT_MAIL_ACCOUNT: bool = False
    SOGO_D_SIGNATURE_SIZE_LIMIT: int = 200
    SOGO_D_ALLOW_EXT_AVATAR: bool = True
    SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED: list[int] = [0, 1, 2, 5, 10, 20, 30, 60]
    SOGO_D_MAIL_JUNK_SETTINGS: str = ""
    SOGO_D_MAIL_JUNK_MAIL_SPAM: str = ""
    SOGO_D_MAIL_JUNK_MAIL_HAM: str = ""


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
    is_needed_by_ui = {"SOGO_D_MAIL_PURGE_ALLOW", "SOGO_D_MAIL_PURGE_MIN_DATE",
                       "SOGO_D_MAIL_FILTERING_ENABLED", "SOGO_D_VACATION_ENABLED",
                       "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS", "SOGO_D_FORWARD_ENABLED",
                       "SOGO_D_NOTIFY_ENABLED", "SOGO_D_MAIL_MAX_RECIPIENT", "SOGO_D_MAIL_DRAFT_AUTOSAVE"}

    SOGO_D_MAIL_SERVER_TYPE = fields.String(load_default="imap", dump_default="imap", validate=validate.OneOf(('imap',))) #Could be jmap in the future...
    SOGO_D_IMAP_SERVER = fields.String() #Hostname or ip of the imap server
    SOGO_D_IMAP_PORT = fields.Integer(load_default=143, dump_default=143, validate=validate.Range(min=1, max=65535))
    SOGO_D_IMAP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(cs.SOCK_ENC_LIST))
    SOGO_D_IMAP_AUTH_MECH =  fields.String(load_default="login", dump_default="login", validate=validate.OneOf(('login', 'plain', 'xoauth2')))
    SOGO_D_MAIL_INBOX = fields.String(load_default="INBOX", dump_default="INBOX") #Name of the inbox folder, cannot be change by user
    SOGO_D_MAIL_SENT = fields.String(load_default="Sent", dump_default="Sent") #Name of the Sent folder
    SOGO_D_MAIL_DRAFT = fields.String(load_default="Drafts", dump_default="Drafts") #Name of the Draft folder
    SOGO_D_MAIL_TRASH = fields.String(load_default="Trash", dump_default="Trash") #Name of the Trash folder
    SOGO_D_MAIL_JUNK = fields.String(load_default="Junk", dump_default="Junk") #Name of the Junk folder
    SOGO_D_MAIL_TEMPLATE = fields.String(load_default="Templates", dump_default="Templates") #Name of the Junk folder
    SOGO_D_SOFT_EMAIL_QUOTA = fields.Integer(load_default=10000, dump_default=10000, validate=validate.Range(min=1, max=10000)) #Percentage multiplier of the true quota as an integer between 1 (0.01%) and 10000 (100%)
    SOGO_D_MAIL_PURGE_ALLOW     = fields.Boolean(load_default=True, dump_default=True) #Allow user to purger their folder (delete all before a date)
    SOGO_D_MAIL_PURGE_MIN_DATE  = fields.Integer(load_default=0, dump_default=0) #Minimum age in days that a user can purge their mail (0 means they can purge everything)
    SOGO_D_MAIL_DRAFT_AUTOSAVE = fields.Integer(load_default=5, dump_default=5, validate=validate.Range(min=5)) #Time in seconds between 2 autosave of a draft.

    SOGO_D_MAIL_FILTERING_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set autoreply sieve rule
    SOGO_D_MAIL_FILTERING_TYPE = fields.String(load_default="sieve", dump_default="sieve", validate=validate.OneOf(('sieve',))) #For sendmail, look at SOGO_S_SENDMAIL
    SOGO_D_SIEVE_SERVER = fields.String() #Hostname or ip of the sieve server
    SOGO_D_SIEVE_PORT = fields.Integer(load_default=4190 , dump_default=4190 , validate=validate.Range(min=1, max=65535))
    SOGO_D_SIEVE_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(cs.SOCK_ENC_LIST))
    SOGO_D_SIEVE_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('plain', 'xoauth2')))
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
    SOGO_D_SMTP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(cs.SOCK_ENC_LIST))

    SOGO_D_SMTP_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'plain', 'xoauth2', 'oauthbearer')))

    SOGO_D_SMTP_MASTER_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Use a master account for system message (notif, event) instead of using the user account
    SOGO_D_SMTP_MASTER_FROM = fields.Email() #Custom from used for system message (password recovery for now)
    SOGO_D_SMTP_MASTER_LOGIN = fields.String()
    SOGO_D_SMTP_MASTER_PWD = fields.String()
    #Mailing -> Settings should be defined by the smtp server. But theyr are here to avoid making a smtp requets and reflect its rules.
    #SOGO_D_MAIL_MAX_SUBMISSION: max mail a user can send during SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL second. If limit is reach, it will be block for
    #SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl seconds. SOGO_D_MAIL_MAX_SUBMISSION = 0 disable any checking.
    #USE ZADD and ZMEMORYRANGE in redis
    SOGO_D_MAIL_MAX_SUBMISSION                = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0))
    SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL       = fields.Integer(load_default=30, dump_default=30, validate=validate.Range(min=10))
    SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl = fields.Integer(load_default=300, dump_default=300, validate=validate.Range(min=5))
    #TODO: for this kind of case, add a param to define exempt uid? For exemple a ressource room that could send a lot of mail...
    SOGO_D_MAIL_MAX_RECIPIENT = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #0 means no limit
    SOGO_D_MAIL_CHECK_FROM = fields.Boolean(load_default=False, dump_default=False) #Make sogo check that the from is one of the user's mail (default, aliases, identities...)


class MailSettingsObj(SettingsObj):
    """
    Obj with the fields of schema MailSettings as attributes with the proper type.
    """

    SOGO_D_MAIL_SERVER_TYPE: str = "imap"
    SOGO_D_IMAP_SERVER: str = ""
    SOGO_D_IMAP_PORT: int = 143
    SOGO_D_IMAP_ENCRYPTION: str = "None"
    SOGO_D_IMAP_AUTH_MECH: str = "None"
    SOGO_D_SOFT_EMAIL_QUOTA: int = 10000
    SOGO_D_MAIL_INBOX: str = "INBOX"
    SOGO_D_MAIL_SENT: str = "Sent"
    SOGO_D_MAIL_DRAFT: str = "Drafts"
    SOGO_D_MAIL_TRASH: str = "Trash"
    SOGO_D_MAIL_JUNK: str = "Junk"
    SOGO_D_MAIL_TEMPLATE: str = "Templates"
    SOGO_D_MAIL_PURGE_ALLOW: bool = True
    SOGO_D_MAIL_PURGE_MIN_DATE: int = 0
    SOGO_D_MAIL_DRAFT_AUTOSAVE: int = 5
    SOGO_D_MAIL_FILTERING_ENABLED: bool = True
    SOGO_D_MAIL_FILTERING_TYPE: str = "sieve"
    SOGO_D_SIEVE_SERVER: str = ""
    SOGO_D_SIEVE_PORT: int = 4190
    SOGO_D_SIEVE_ENCRYPTION: str = "None"
    SOGO_D_SIEVE_AUTH_MECH: str = "None"
    SOGO_D_SIEVE_FOLDER_ENCODING: str = "utf-7"
    SOGO_D_SIEVE_HEADER: str = ""
    SOGO_D_SIEVE_FOOTER: str = ""
    SOGO_D_SIEVE_FIRST_FILTER: str = ""
    SOGO_D_VACATION_ENABLED: bool = True
    SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS: bool = False
    SOGO_D_FORWARD_ENABLED: bool = True
    SOGO_D_FORWARD_ALLOW_USER_DOMAIN: bool = True
    SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN: bool = True
    SOGO_D_FORWARD_ALLOW_EXT_DOMAIN: bool = True
    SOGO_D_FORWARD_WHITELIST: list[str] = []
    SOGO_D_FORWARD_BLACKLIST: list[str] = []
    SOGO_D_NOTIFY_ENABLED: bool = True
    SOGO_D_NOTIFY_ALLOW_USER_DOMAIN: bool = True
    SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN: bool = True
    SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN: bool = True
    SOGO_D_NOTIFY_WHITELIST: list[str] = []
    SOGO_D_NOTIFY_BLACKLIST: list[str] = []
    SOGO_D_MAIL_OUTGOING_TYPE: str = "smtp"
    SOGO_D_SMTP_SERVER: str = ""
    SOGO_D_SMTP_PORT: int = 584
    SOGO_D_SMTP_ENCRYPTION: str = "None"
    SOGO_D_SMTP_AUTH_MECH: str = "None"
    SOGO_D_SMTP_MASTER_ENABLED: bool = False
    SOGO_D_SMTP_MASTER_LOGIN: str = ""
    SOGO_D_SMTP_MASTER_PWD: str = ""
    SOGO_D_MAIL_MAX_SUBMISSION: int = 0
    SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL: int = 30
    SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl: int = 300
    SOGO_D_MAIL_MAX_RECIPIENT: int = 0
    SOGO_D_MAIL_SYSTEM_FROM: str = ""

    def get_mail_server_settings_for_type(self, type_server: str) -> dict:
        """
        return the proper dict config for this type of mail server

        :param type: _description_
        :type type: str
        :raises AggravatedException: _description_
        :return: _description_
        :rtype: dict
        """
        if type_server == "imap":
            return {
                "server": self.SOGO_D_IMAP_SERVER,
                "port": self.SOGO_D_IMAP_PORT,
                "encryption": self.SOGO_D_IMAP_ENCRYPTION,
                "auth_mech": self.SOGO_D_IMAP_AUTH_MECH,
                "folders_map": {
                    cs.MAIL_FOLDER_INBOX: self.SOGO_D_MAIL_INBOX,
                    cs.MAIL_FOLDER_SENT: self.SOGO_D_MAIL_SENT,
                    cs.MAIL_FOLDER_DRAFT: self.SOGO_D_MAIL_DRAFT,
                    cs.MAIL_FOLDER_JUNK: self.SOGO_D_MAIL_JUNK,
                    cs.MAIL_FOLDER_TRASH: self.SOGO_D_MAIL_TRASH,
                    cs.MAIL_FOLDER_TEMPLATE: self.SOGO_D_MAIL_TEMPLATE,
                }
            }
        raise AggravatedException(err.ERROR_CONFIG_WRONG_MAIL_SERVER.m, err.ERROR_CONFIG_WRONG_MAIL_SERVER)

    def get_mail_filtering_settings_for_type(self, type_filtering: str) -> dict:
        """
        Get the mail server settings for a specific filtering type.

        :param type_filtering: The filtering type (e.g., "sieve")
        :return: A dictionary with the mail server settings
        """
        if type_filtering == "sieve":
            return {
                "server": self.SOGO_D_SIEVE_SERVER,
                "port": self.SOGO_D_SIEVE_PORT,
                "encryption": self.SOGO_D_SIEVE_ENCRYPTION,
                "auth_mech": self.SOGO_D_SIEVE_AUTH_MECH,
                
            }
        raise AggravatedException(err.ERROR_CONFIG_WRONG_MAIL_FILTERING.m, err.ERROR_CONFIG_WRONG_MAIL_FILTERING)

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
    is_needed_by_ui = {"SOGO_D_CALDAV_ENABLED", "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE",
                       "SOGO_D_CARDAV_ENABLED", "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE",
                       "SOGO_D_JITSI_LINK_ENABLED", "SOGO_D_JITSI_BASE_URL",
                       "SOGO_D_REMINDER_ALLOW_MAIL", "SOGO_D_CALENDAR_PUBLIC_LINK_ENABLED"}

    SOGO_D_CALDAV_ENABLED = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE = fields.Boolean(load_default=False, dump_default=False) #Enable or not public caldav access
    SOGO_D_CALDAV_START_TIME  = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #limit the the span of time of the events return in a caldav request
                                                                                                               #0 means no limit, 180 means only events that are less than 180 days olds are returned.

    SOGO_D_CARDAV_ENABLED  = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE = fields.Boolean(load_default=False, dump_default=False) #Enable or not public cardav access

    SOGO_D_JITSI_LINK_ENABLED = fields.Boolean(load_default=True, dump_default=True)
    SOGO_D_JITSI_BASE_URL     = fields.Url(load_default="https://meet.jit.si", dump_default="https://meet.jit.si", schemes={'http','https'})

    SOGO_D_REMINDER_ALLOW_MAIL = fields.Boolean(load_default=True, dump_default=True) #Allow user to set reminder sent by email for events/tasks

    SOGO_D_CALENDAR_PUBLIC_LINK_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to expose a calendar through a public .ics subscription URL

class CalendarContactSettingsObj(SettingsObj):
    """
    Obj with the fields of schema CalendarContactSettings as attributes with the proper type.
    """

    SOGO_D_CALDAV_ENABLED: bool = True
    SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE: bool = False
    SOGO_D_CALDAV_START_TIME: int = 0
    SOGO_D_CARDAV_ENABLED: bool = True
    SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE: bool = False
    SOGO_D_JITSI_LINK_ENABLED: bool = True
    SOGO_D_JITSI_BASE_URL: str = ""
    SOGO_D_CALENDAR_PUBLIC_LINK_ENABLED: bool = True
    SOGO_D_REMINDER_ALLOW_MAIL: bool = True
