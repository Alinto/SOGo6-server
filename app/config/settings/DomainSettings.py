# -*- coding: utf-8 -*-

"""
Defines all domains parameters
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, post_load, post_dump

class SymmetricKey(Schema):
    """
    Schema for symmetric key when a cryptographic algo needs one
    There is three ways to store the SYM
    SIM_KEY_TYPE = 'path'
    SIM_KEY_VALUE = 'path/to/file/with/sim.key'

    SIM_KEY_TYPE = 'env'
    SIM_KEY_VALUE = 'NAME_OF_ENV_VAR_WITH_SIM'

    SIM_KEY_TYPE = 'plain'
    SIM_KEY_VALUE = 'value_of_sim_key'
    """
    SIM_KEY_TYPE  = fields.String(validate=validate.OneOf(('path', 'env', 'plain')))
    SIM_KEY_VALUE = fields.String()

class PasswordPolicy(Schema):
    """
    Schema for the password policies
    """
    PW_LEN_MIN = fields.Integer(load_default=1, dump_default=1,validate=validate.Range(min=1)) #Minimum lenght of password
    PW_LEN_MAX = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Maximum lenght of password, 0 means no limit
    PW_UPPERCASE = fields.Integer(load_default=0, dump_default=0,validate=validate.Range(min=0)) #Minimum number of uppercase letter, 0 means no need
    #TODO the rest...

#As it was often written "ldap fields or SQL columns", a shorcut was made: "sqldap field"
class UserSource(Schema):
    """
    Schema for an agnostic User Source
    """
    US_TYPE = fields.String(required=True, validate=validate.OneOf(('ldap', 'sql'))) #Type of the user source
    US_ID   = fields.String(required=True) #must be unique

    US_MAIL       = fields.List(fields.String(), load_default=['mail'], dump_default=['mail']) #Name of the sqldap field with the user's mail/alias
    US_SEARCH     = fields.List(fields.String()) #Array of sqldap field used for autocompletion/search of user

    #TODO change name to somethinf agnostic? Or later add parameter for Jmap...
    US_IMAP_LOGIN = fields.String() #sqldap field where to fetch the imap login for a user (default to UIDFieldName for ldap or c_uid for sql)
    US_SMTP_LOGIN = fields.String() #sqldap field where to fecth the smtp login for a user (default to UIDFieldName for ldap or c_uid for sql)

    US_PWD_ALGO         = fields.String() #TODO Algo used to encrypt the user password for login (sql) and when changing password (sql/ldap). Decide which algo bases on SOGo5 ones.
    US_PWD_ALGO_SIM_KEY = fields.Nested(SymmetricKey)

    US_CAN_AUTH       = fields.Boolean(required=True) #The users in this US can authenticate
    US_IS_ADDRESSBOOK = fields.Boolean(required=True) #This US is shown for autocompletion and shared address book
                                                      #Why make a user source that can't auth and is not an address book?
                                                      #Sogo will still known this user source and considere it internal (interlal domain vs external)
    US_DISPLAY_NAME   = fields.String() #HUman readable name og this US, will ude US_ID if not set
    US_AUTO_SEARCH    = fields.Boolean(load_default=False, dump_default=False) #Auto return all users of the US whitout typing any char in the search bar.

    US_AUTO_QUERY_LIMIT = fields.Integer(load_default=0, dump_default=0) #Maximum result return for a autocompletion query, default to 0 means no limit.
    US_EXTRA_CONTACT_INFO = fields.String() #sqladp field to show when doing autocompletion (will be "cn <extra> mail")

    US_PASSWORD_POLICY = fields.Nested(PasswordPolicy) #Policies on password CAREFUL CONFLICT WITH LDAP_PWD_POLICY

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

    LDAP_QUERY_TIMEOUT = fields.Integer(dump_default=0, load_default=0, validate=validate.Range(min=0)) #Used as parameter by ldap query method. 0 means no limit


    LDAP_BIND_DN      = fields.String(required=True)#The bind DN used to authnetify against the ldap server
    LDAP_BIND_PWD     = fields.String(required=True) #The password for the bindDN
    LDAP_BIND_AS_USER = fields.Boolean(load_default=False, dump_default=False) #After the fist auth, use the user's DN for the bind DN
    LDAP_BIND_FIELD   = fields.List(fields.String())  #Additionnal field to use when doing a bind
    LDAP_LOOKUP_FIELD = fields.List(fields.String(), load_default=['*'], dump_default=['*'])
    LDAP_GROUP_CLASS  = fields.List(fields.String(), load_default=['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'],
                                                     dump_default=['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'])

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
    SQL_USER_URL           = fields.Url(required=True, schemes={"mysql", "postgresql"}) #database uri to the user source
    SQL_PREPEND_PWD_SCHEME = fields.Boolean(required=True) #should the password be stored in the dabase with the shceme like this {scheme)encrypteValue
    SQL_USER_FILTER        = fields.String() #Additional filter to add at the where clause when querying users.
    SQL_DOMAIN_FIELD       = fields.String() #Fields where the user's domain is.

    US_SEARCH     = fields.List(fields.String(), load_default=['mail', 'c_cn']) #Array of sqldap field used for autocompletion/search of user
    US_IMAP_LOGIN = fields.String(load_default="c_uid", dump_default="c_uid") ##sql column where to fetch the imap login for a user

    @validates_schema
    def check_type(self, data, **_):
        """
        Check the type of User Source
        """
        if data["TYPE"] != "sql":
            raise ValidationError("SQLUserSource set without TYPE being 'sql'")


class OutgoinMail(Schema):
    """
    Schema for outgoin mail server
    """
    MAILING_TYPE = fields.String(required=True, validate=validate.OneOf({'smtp', 'sendmail'}))

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

    #If SOGO_D_AUTH_TYPE = 'openid'
    SOGO_D_OPENID_CONFIG_URL           = fields.Url(schemes={'http','https'})
    SOGO_D_OPENID_CLIENT_NAME          = fields.String() #Name of the openid client
    SOGO_D_OPENID_CLIENT_SECRET        = fields.String() #Secret of the openid client #TODO in post/pre processing, encrypt/decrypt the secret
    SOGO_D_OPENID_SCOPE                = fields.String(load_default="openid profile email", dump_default="openid profile email") #Scope requested to the openis server
    SOGO_D_OPENID_EMAIL                = fields.String(load_default="email", dump_default="email") #parameter from user profile with the user's mail, to match with the user source
    SOGO_D_OPENID_TOKEN_CHECK_INTERVAL = fields.Integer(validate=validate.Range(min=0)) #Interval where a valid token is not checked again. 0 means always checked.

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
                                                                                                                            #TODO make sure that the front wait for a bit before doing the search, like waiting for the user to have ending its typing
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
    #TODO: for this kind of case, add a param to define exempt uid? For exemple a ressource room that could send a lot of mail...

    #Mailing pure sogo
    SOGO_D_MAIL_PURGE_ALLOW     = fields.Boolean(load_default=True, dump_default=True) #Allow user to purger their folder (delete all before a date)
    SOGO_D_MAIL_PURGE_MIN_DATE  = fields.Integer(load_default=0, dump_default=0) #Minimum age in days that a user can purge their mail (0 means they can purge everything)

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

    SOGO_D_USERSOURCE = fields.Nested(UserSource)


    #OUTGOING
    SOGO_D_SEND_MAIL_TYPE = fields.String(load_default="smtp", dump_default="smtp", validate=validate.OneOf(('smtp', 'sendmail'))) #For sendmail, look at SOGO_S_SENDMAIL

    #SMTP settings
    SOGO_D_SMTP_SERVER = fields.String() #Hostname or ip of the smtp server
    SOGO_D_SMTP_PORT = fields.Integer(load_default=587, dump_default=584, validate=validate.Range(min=1, max=65535))
    SOGO_D_SMTP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'TLS', 'SSL')))
    SOGO_D_SMTP_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'plain', 'xoauth2')))
    SOGO_D_SMTP_MASTER_ENABLED = fields.Boolean(load_default=False, dump_default=False)
    SOGO_D_SMTP_MASTER_MAIL = fields.String() #Required if SOGO_D_SMTP_MASTER_ENABLED = TRUE
    SOGO_D_SMTP_MASTER_PWD = fields.String()  #Required if SOGO_D_SMTP_MASTER_ENABLED = TRUE

    #INGOING
    SOGO_D_READ_MAIL_TYPE = fields.String(load_default="imap", dump_default="imap", validate=validate.OneOf(('imap'))) #Could be jmap in the future...
    SOGO_D_SOFT_EMAIL_QUOTA = fields.Integer(load_default=1, dump_default=1, validate=validate.Range(min=0, max=1, min_inclusive=False)) #Multiplier to the true quota for the user

    #IMAP (and SIEVE) SETTINGS
    SOGO_D_IMAP_SERVER = fields.String() #Hostname or ip of the imap server
    SOGO_D_IMAP_PORT = fields.Integer(load_default=143, dump_default=143, validate=validate.Range(min=1, max=65535))
    SOGO_D_IMAP_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'TLS', 'SSL')))
    SOGO_D_SIEVE_SERVER = fields.String() #Hostname or ip of the sieve server
    SOGO_D_SIEVE_PORT = fields.Integer(load_default=4190 , dump_default=4190 , validate=validate.Range(min=1, max=65535))
    SOGO_D_SIEVE_ENCRYPTION = fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'TLS', 'SSL')))
    SOGO_D_IMAP_AUTH_MECH =  fields.String(load_default="None", dump_default="None", validate=validate.OneOf(('None', 'plain', 'xoauth2')))
    SOGO_D_SIEVE_FOLDER_ENCODING = fields.String(load_default="utf-7", dump_default="utf-7", validate=validate.OneOf(('utf-7', 'utf-8')))
    SOGO_D_IMAP_POOLING_ENABLE = fields.Boolean(load_default=False, dump_default=False) #Automaticcaly logout from imap connection
    SOGO_D_IMAP_POOLING_TIME = fields.Integer(load_default=300, dump_default=300, validate=validate.Range(min=1, max=65535))

    #Identities
    SOGO_D_IDENTITIES_ENABLED = fields.Boolean(load_default=False, dump_default=False) #Allow users to create identities for their main imap account

    #Webmail
    SOGO_D_ALLOW_EXT_AVATAR = fields.Boolean(load_default=True, dump_default=True) #Allow users to load external avatar
    SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED = fields.List(fields.Integer(validate=validate.OneOf((0, 1, 2, 5, 10, 20, 30, 60))),
                                                     load_default=[0, 1, 2, 5, 10, 20, 30, 60],
                                                     dump_default=[0, 1, 2, 5, 10, 20, 30, 60])

    #Sieve
    SOGO_D_SIEVE_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set autoreply sieve rule
    SOGO_D_SIEVE_HEADER = fields.Dict() #Sieve script that will be set for each user sieve script at the top level
    SOGO_D_SIEVE_FOOTER = fields.Dict() #Sieve script that will be set for each user sieve script at the bottom level
    SOGO_D_SIEVE_FIRST_FILTER = fields.Dict() #Sieve script that will set for new users

    SOGO_D_VACATION_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set autoreply sieve rule
    SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS = fields.Boolean(load_default=False, dump_default=False) #Allow users to set a zero day for vacation message (meaning it always auroreply)

    SOGO_D_FORWARD_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule
    SOGO_D_FORWARD_ALLOW_USER_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule towards its own domain
    SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule towards other sogo's domains
    SOGO_D_FORWARD_ALLOW_EXT_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set forward sieve rule towards external domains
    SOGO_D_FORWARD_WHITELIST = fields.List(fields.String()) #Whitelist for forward sieve rule
    SOGO_D_FORWARD_WHITELIST = fields.List(fields.String()) #Blacklist for forward sieve rule

    SOGO_D_NOTIFY_ENABLED = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule
    SOGO_D_NOTIFY_ALLOW_USER_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule towards its own domain
    SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule towards other sogo's domains
    SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN = fields.Boolean(load_default=True, dump_default=True) #Allow users to set notify sieve rule towards external domains
    SOGO_D_NOTIFY_WHITELIST = fields.List(fields.String()) #Whitelist for notify sieve rule
    SOGO_D_NOTIFY_WHITELIST = fields.List(fields.String()) #Blacklist for notify sieve rule
    


    @validates_schema(skip_on_field_errors=True)
    def validate_auth_settings(self, data: dict, **_):
        """
        If SOGO_D_AUTH_TYPE = 'cas', check the other value
        """
        if data["SOGO_D_AUTH_TYPE"] == "cas":
            if {"SOGO_D_CAS_URL", "SOGO_D_CAS_LOGOUT_ENABLED"} not in set(data):
                raise ValidationError("Parameters among 'SOGO_D_CAS_URL', 'SOGO_D_CAS_LOGOUT_ENABLED' are missing")

    @validates_schema(skip_on_field_errors=True)
    def validate_smtp_settings(self, data: dict, **_):
        """
        If SOGO_D_AUTH_TYPE = 'cas', check the other value
        """
        if data["SOGO_D_SEND_MAIL_TYPE"] == "smtp":
            if "SOGO_D_SMTP_SERVER" not in set(data):
                raise ValidationError("Parameter 'SOGO_D_SMTP_SERVER' is missing")
        
        if data["SOGO_D_SMTP_MASTER_ENABLED"]:
            if {"SOGO_D_SMTP_MASTER_MAIL", "SOGO_D_SMTP_MASTER_PWD"} not in set(data):
                raise ValidationError("Parameter 'SOGO_D_SMTP_MASTER_MAIL' SOGO_D_SMTP_MASTER_PWD are not set")


